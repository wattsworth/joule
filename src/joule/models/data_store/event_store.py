import asyncpg
import json
import datetime
from typing import List, Optional, TYPE_CHECKING, Dict, Callable, Tuple

from joule.models.data_store import psql_helpers
import joule.utilities

if TYPE_CHECKING:
    from joule.models import EventStream


class EventStore:

    def __init__(self, dsn=""):
        self.dsn = dsn
        self.pool = None

    async def initialize(self, pool=None) -> None:
        if pool is None:
            if self.dsn == "":
                raise ValueError("Must specify either dsn or pool")
            self.pool = await asyncpg.create_pool(self.dsn, command_timeout=60)
        else:
            self.pool = pool
        async with self.pool.acquire() as conn:
            await psql_helpers.create_event_table(conn)

    async def upsert(self, stream: 'EventStream', events: List):
        updated_events = list(filter(lambda event: "id" in event and event["id"] is not None, events))
        new_events = list(filter(lambda event: "id" not in event or event["id"] is None, events))
        async with self.pool.acquire() as conn:
            if len(new_events) > 0:
                seq = "'data.events_id_seq'"
                query = await conn.fetch(
                    f"select setval({seq},nextval({seq}) + {len(new_events)} -1) as stop")

                serial = query[0]["stop"] - len(new_events)

                for e in new_events:
                    serial += 1
                    e["id"] = serial
                assert serial == query[0]["stop"]
                mapper = map(event_to_record_mapper(stream), new_events)
                await conn.copy_records_to_table("events",
                                                 columns=['id', 'time', 'end_time', 'event_stream_id', 'content'],
                                                 schema_name='data',
                                                 records=mapper)
            if len(updated_events) > 0:
                mapper = map(event_to_record_mapper(stream), updated_events)
                for e in mapper:
                    await conn.execute("UPDATE data.events SET time=$2, "
                                       "end_time=$3, event_stream_id=$4, "
                                       "content=$5 WHERE id=$1",
                                       *e)
        return events

    async def count(self, stream: 'EventStream',
                    start: Optional[int] = None, end: Optional[int] = None,
                    json_filter=None) -> int:
        if end is not None and start is not None and end <= start:
            raise ValueError("Invalid time bounds start [%d] must be < end [%d]" % (start, end))
        query = "SELECT count(*) FROM data.events "
        where_clause = psql_helpers.query_time_bounds(start, end,
                                                      start_col_name='time',
                                                      end_col_name='end_time')
        if len(where_clause) == 0:
            where_clause = "WHERE "
        else:
            where_clause += " AND "
        where_clause += "event_stream_id=%d" % stream.id
        if json_filter is not None and len(json_filter) > 0:
            where_clause += " AND " + psql_helpers.query_event_json(json_filter)
        query += where_clause
        async with self.pool.acquire() as conn:
            record = await conn.fetch(query)
            return record[0]['count']

    async def histogram(self, stream: 'EventStream',
                        start: Optional[int] = None, end: Optional[int] = None,
                        json_filter=None,
                        nbuckets=100) -> List[Dict]:
        if end is not None and start is not None and end <= start:
            raise ValueError("Invalid time bounds start [%d] must be < end [%d]" % (start, end))
        # if start or end are omitted use the beginning/end of the dataset
        async with self.pool.acquire() as conn:
            if end is None:
                query = "SELECT time FROM data.events ORDER BY time DESC LIMIT 1"
                end = (await conn.fetch(query))
                if len(end) == 0:
                    return []  # no data
                end = end[0]['time']
            elif type(end) is not datetime.datetime:
                end = datetime.datetime.fromtimestamp(end / 1e6, tz=datetime.timezone.utc).replace(tzinfo=None)
            if start is None:
                query = "SELECT time FROM data.events ORDER BY time ASC LIMIT 1"
                start = (await conn.fetch(query))[0]['time']
            elif type(start) is not datetime.datetime:
                start = datetime.datetime.fromtimestamp(start / 1e6, tz=datetime.timezone.utc).replace(tzinfo=None)
            bucket_size = ((end - start) / (nbuckets - 1)).total_seconds()
            query = f"""SELECT time_bucket_gapfill('{bucket_size}s', time) AS bucket, COALESCE(count(*),0) AS count
                       FROM data.events
                       WHERE time >= $1 AND time <= $2
                       AND event_stream_id=$3"""
            if json_filter is not None and len(json_filter) > 0:
                query += " AND " + psql_helpers.query_event_json(json_filter)
            query += " GROUP BY bucket ORDER BY bucket ASC"
            records = await conn.fetch(query, start, end, stream.id)
            return histogram_to_events(records)
            #return [(joule.utilities.datetime_to_timestamp(r['bucket']), r['count']) for r in records]

    async def extract(self, stream: 'EventStream',
                      start: Optional[int] = None,
                      end: Optional[int] = None,
                      json_filter=None,
                      limit=None) -> List[Dict]:
        if end is not None and start is not None and end <= start:
            raise ValueError("Invalid time bounds start [%d] must be < end [%d]" % (start, end))
        query = "SELECT id, time, end_time, content FROM data.events "
        where_clause = psql_helpers.query_time_bounds(start, end,
                                                      start_col_name='time',
                                                      end_col_name='end_time')
        if len(where_clause) == 0:
            where_clause = "WHERE "
        else:
            where_clause += " AND "
        where_clause += "event_stream_id=%d" % stream.id
        if json_filter is not None and len(json_filter) > 0:
            where_clause += " AND " + psql_helpers.query_event_json(json_filter)
        query += where_clause
        if limit is not None:
            assert limit > 0, "limit must be > 0"
            if start is None and end is not None:
                query += " ORDER BY time DESC"
            else:
                query += " ORDER BY time ASC"
            query += f" LIMIT {limit}"
        else:
            query += " ORDER BY time ASC"
        async with self.pool.acquire() as conn:
            records = await conn.fetch(query)
            events = list(map(record_to_event, records))
            events.sort(key=lambda e: e["start_time"])
            return events

    async def remove(self, stream: 'EventStream', start: Optional[int] = None,
                     end: Optional[int] = None,
                     json_filter=None):
        query = "DELETE FROM data.events "
        where_clause = psql_helpers.query_time_bounds(start, end,
                                                      start_col_name='time',
                                                      end_col_name='end_time')
        if len(where_clause) == 0:
            where_clause = "WHERE "
        else:
            where_clause += " AND "
        where_clause += "event_stream_id=%d" % stream.id
        if json_filter is not None and len(json_filter) > 0:
            where_clause += " AND " + psql_helpers.query_event_json(json_filter)
        query += where_clause
        async with self.pool.acquire() as conn:
            return await conn.execute(query)

    async def destroy(self, stream: 'EventStream'):
        await self.remove(stream)

    async def info(self, streams: List['EventStream']) -> Dict[int, 'StreamInfo']:
        if len(streams) == 0:
            return {}  # no event streams
        info_objects = {s.id: StreamInfo(None, None, 0, 0, 0) for s in streams}
        async with self.pool.acquire() as conn:
            query = "select count(*), event_stream_id, max(time) as end_time," \
                    " min(time) as start_time from data.events "
            if len(streams) < 10:
                stream_ids = ','.join([str(s.id) for s in streams])
                query += f"where event_stream_id in ({stream_ids}) "
            query += "group by event_stream_id"
            rows = await conn.fetch(query)
            for row in rows:
                if row['event_stream_id'] in info_objects.keys():
                    end_time = joule.utilities.datetime_to_timestamp(row['end_time'])
                    start_time = joule.utilities.datetime_to_timestamp(row['start_time'])
                    total_time = end_time - start_time
                    total_bytes = 0  # TODO
                    info_objects[row['event_stream_id']] = StreamInfo(start_time, end_time, row['count'],
                                                                      total_time, total_bytes)
        return info_objects

    async def close(self):
        await self.pool.close()


class StreamInfo:
    def __init__(self, start: Optional[int], end: Optional[int], event_count: int,
                 total_time: int = 0, bytes: int = 0):
        self.start = start
        self.end = end
        self.event_count = event_count
        self.bytes = bytes
        self.total_time = total_time

    def __repr__(self):
        return "<StreamInfo start=%r end=%r event_count=%r, total_time=%r>" % (
            self.start, self.end, self.event_count, self.total_time)

    def __eq__(self, other):
        return self.start == other.start and \
               self.end == other.end and \
               self.event_count == other.event_count and \
               self.bytes == other.bytes and \
               self.total_time == other.total_time

    def to_json(self):
        return {
            "start": self.start,
            "end": self.end,
            "event_count": self.event_count,
            "bytes": self.bytes,
            "total_time": self.total_time
        }


def event_to_record_mapper(stream: 'EventStream') -> Callable[[Dict], Tuple]:
    stream_id = stream.id

    def mapper(event: Dict) -> Tuple:
        start = joule.utilities.timestamp_to_datetime(event['start_time'])
        if event['end_time'] is not None:
            if event['start_time'] >= event['end_time']:
                raise ValueError("Event end [%d] cannot be before start [%d]" % (
                    event['start_time'], event['end_time']
                ))
            end = joule.utilities.timestamp_to_datetime(event['end_time'])
        else:
            end = None
        return event["id"], start, end, stream_id, json.dumps(event['content'])

    return mapper


def record_to_event(record: asyncpg.Record) -> Dict:
    if record['end_time'] is not None:
        end = joule.utilities.datetime_to_timestamp(record['end_time'])
    else:
        end = None
    return {
        'id': record['id'],
        'start_time': joule.utilities.datetime_to_timestamp(record['time']),
        'end_time': end,
        'content': json.loads(record['content'])}


def histogram_to_events(histogram: List[Tuple[int, int]]) -> List[Dict]:
    events = []
    for i in range(len(histogram) - 1):
        events.append({
            "id": -1,  # not used
            "start_time": joule.utilities.datetime_to_timestamp(histogram[i][0]),
            "end_time": joule.utilities.datetime_to_timestamp(histogram[i + 1][0]),
            "content": {"count": histogram[i][1]}})
    events.append({
        "id": -1,  # not used
        "start_time": joule.utilities.datetime_to_timestamp(histogram[-1][0]),
        "end_time": joule.utilities.datetime_to_timestamp(histogram[-1][0]),
        "content": {"count": histogram[-1][1]}})
    return events
