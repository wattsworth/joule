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

    async def create(self, stream: 'EventStream'):
        async with self.pool.acquire() as conn:
            await psql_helpers.create_event_table(conn, stream)

    async def upsert(self, stream: 'EventStream', events: List):
        updated_events = list(filter(lambda event: "id" in event and event["id"] is not None, events))
        new_events = list(filter(lambda event: "id" not in event or event["id"] is None, events))
        async with self.pool.acquire() as conn:
            # lazy stream creation, does nothing if stream already exists
            # keep for legacy nodes, current implementation creates tables at stream creation
            await psql_helpers.create_event_table(conn, stream)
            if len(new_events) > 0:
                seq = f"'data.event{stream.id}_id_seq'"
                query = await conn.fetch(
                    f"select setval({seq},nextval({seq}) + {len(new_events)} -1) as stop")

                serial = query[0]["stop"] - len(new_events)

                for e in new_events:
                    serial += 1
                    e["id"] = serial
                assert serial == query[0]["stop"]
                await conn.copy_records_to_table(f"event{stream.id}",
                                                 columns=['id',
                                                          'start_time',
                                                          'end_time',
                                                          'content'],
                                                 schema_name='data',
                                                 records=map(event_to_record, new_events))
            query = f"UPDATE data.event{stream.id} SET start_time=$2, end_time=$3, content=$4 WHERE id=$1"
            if len(updated_events) > 0:
                mapper = map(event_to_record, updated_events)
                for e in mapper:
                    await conn.execute(query, *e)
        return events

    async def count(self, stream: 'EventStream',
                    start: Optional[int] = None, end: Optional[int] = None,
                    json_filter=None,
                    include_on_going_events=False) -> int:
        if end is not None and start is not None and end <= start:
            raise ValueError("Invalid time bounds start [%d] must be < end [%d]" % (start, end))
        query = f"SELECT count(*) FROM data.event{stream.id} "
        if include_on_going_events:
            end_col_name = None  # only return events that start within this interval
        else:
            end_col_name = 'end_time'  # return all events that are active within this interval
        where_clauses = [psql_helpers.query_time_bounds(start, end,
                                                        start_col_name='start_time',
                                                        end_col_name=end_col_name)]
        if json_filter is not None and len(json_filter) > 0:
            where_clauses.append(psql_helpers.query_event_json(json_filter))
        where_clauses = [wc for wc in where_clauses if len(wc) > 0]
        if len(where_clauses) > 0:
            query += "WHERE " + " AND ".join(where_clauses)
        try:
            async with self.pool.acquire() as conn:
                record = await conn.fetch(query)
                return record[0]['count']
        except asyncpg.UndefinedTableError: # legacy nodes may not have tables for empty streams
            return 0  # no data

    async def histogram(self, stream: 'EventStream',
                        start: Optional[int] = None, end: Optional[int] = None,
                        json_filter=None,
                        nbuckets=100) -> List[Dict]:
        if end is not None and start is not None and end <= start:
            raise ValueError("Invalid time bounds start [%d] must be < end [%d]" % (start, end))
        # if start or end are omitted use the beginning/end of the dataset
        async with self.pool.acquire() as conn:
            if end is None:
                query = f"SELECT end_time FROM data.event{stream.id} ORDER BY end_time DESC LIMIT 1"
                end = (await conn.fetch(query))
                if len(end) == 0:
                    return []  # no data
                end = end[0]['end_time']
            elif type(end) is not datetime.datetime:
                end = datetime.datetime.fromtimestamp(end / 1e6, tz=datetime.timezone.utc).replace(tzinfo=None)
            if start is None:
                query = f"SELECT start_time FROM data.event{stream.id} ORDER BY start_time ASC LIMIT 1"
                start = (await conn.fetch(query))[0]['start_time']
            elif type(start) is not datetime.datetime:
                start = datetime.datetime.fromtimestamp(start / 1e6, tz=datetime.timezone.utc).replace(tzinfo=None)
            bucket_size = ((end - start) / (nbuckets - 1)).total_seconds()
            query = f"""SELECT time_bucket_gapfill('{bucket_size}s', start_time) AS bucket, COALESCE(count(*),0) AS count
                       FROM data.event{stream.id}
                       WHERE start_time >= $1 AND start_time <= $2"""
            if json_filter is not None and len(json_filter) > 0:
                query += " AND " + psql_helpers.query_event_json(json_filter)
            query += " GROUP BY bucket ORDER BY bucket ASC"
            records = await conn.fetch(query, start, end)
            return histogram_to_events(records)
            # return [(joule.utilities.datetime_to_timestamp(r['bucket']), r['count']) for r in records]

    async def extract(self, stream: 'EventStream',
                      start: Optional[int] = None,
                      end: Optional[int] = None,
                      json_filter=None,
                      limit=None,
                      include_on_going_events=False) -> List[Dict]:
        if end is not None and start is not None and end <= start:
            raise ValueError("Invalid time bounds start [%d] must be < end [%d]" % (start, end))
        query = f"SELECT id, start_time, end_time, content FROM data.event{stream.id} "
        if not include_on_going_events:
            end_col_name = None  # only return events that start within this interval
        else:
            end_col_name = 'end_time'  # return all events that are active within this interval
        where_clauses = [psql_helpers.query_time_bounds(start, end,
                                                        start_col_name='start_time',
                                                        end_col_name=end_col_name)]
        if json_filter is not None and len(json_filter) > 0:
            where_clauses.append(psql_helpers.query_event_json(json_filter))
        where_clauses = [wc for wc in where_clauses if len(wc) > 0]
        if len(where_clauses) > 0:
            query += "WHERE " + " AND ".join(where_clauses)
        if limit is not None:
            assert limit > 0, "limit must be > 0"
            if start is None and end is not None:
                query += " ORDER BY start_time DESC"
            else:
                query += " ORDER BY start_time ASC"
            query += f" LIMIT {limit}"
        else:
            query += " ORDER BY start_time ASC"
        try:
            async with self.pool.acquire() as conn:
                records = await conn.fetch(query)
                events = list(map(record_to_event, records))
                events.sort(key=lambda e: e["start_time"])
                return events
        except asyncpg.UndefinedTableError:  # legacy nodes may not have tables for empty streams
            return []  # no data

    async def remove(self, stream: 'EventStream', start: Optional[int] = None,
                     end: Optional[int] = None,
                     json_filter=None):
        if start is None and end is None and json_filter is None:
            # flush the stream
            try:
                async with self.pool.acquire() as conn:
                    return await conn.execute(f"TRUNCATE data.event{stream.id}")
            except asyncpg.UndefinedTableError:
                pass  # legacy nodes may not have tables for empty streams

        query = f"DELETE FROM data.event{stream.id} "
        where_clauses = [psql_helpers.query_time_bounds(start, end,
                                                        start_col_name='start_time',
                                                        end_col_name='end_time')]
        if json_filter is not None and len(json_filter) > 0:
            where_clauses.append(psql_helpers.query_event_json(json_filter))
        where_clauses = [wc for wc in where_clauses if len(wc) > 0]
        if len(where_clauses) > 0:
            query += " WHERE " + " AND ".join(where_clauses)
        try:
            async with self.pool.acquire() as conn:
                return await conn.execute(query)
        except asyncpg.UndefinedTableError:
            pass  # legacy nodes may not have tables for empty streams

    async def destroy(self, stream: 'EventStream'):
        try:
            async with self.pool.acquire() as conn:
                return await conn.execute(f"DROP TABLE data.event{stream.id}")
        except asyncpg.UndefinedTableError:
            pass  # legacy nodes may not have tables for empty streams

    async def info(self, streams: List['EventStream']) -> Dict[int, 'StreamInfo']:
        if len(streams) == 0:
            return {}  # no event streams
        info_objects = {s.id: StreamInfo(None, None, 0, 0, 0) for s in streams}

        async with self.pool.acquire() as conn:
            for stream in streams:
                try:
                    query = "select count(*), min(start_time) as start_time," \
                            f" max(end_time) as end_time from data.event{stream.id}"
                    row = await conn.fetchrow(query)
                    if row['count'] == 0:
                        continue  # no events in stream
                    end_time = joule.utilities.datetime_to_timestamp(row['end_time'])
                    start_time = joule.utilities.datetime_to_timestamp(row['start_time'])
                    total_time = end_time - start_time
                    total_bytes = 0  # TODO
                    info_objects[stream.id] = StreamInfo(start_time, end_time, row['count'],
                                                         total_time, total_bytes)
                except asyncpg.UndefinedTableError:
                    # this stream has no data tables, leave the record empty
                    pass
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


def event_to_record(event: Dict) -> Tuple:
    start = joule.utilities.timestamp_to_datetime(event['start_time'])
    if event['end_time'] is not None:
        if event['start_time'] >= event['end_time']:
            raise ValueError("Event end [%d] cannot be before start [%d]" % (
                event['start_time'], event['end_time']
            ))
        end = joule.utilities.timestamp_to_datetime(event['end_time'])
    else:
        end = None
    return event["id"], start, end, json.dumps(event['content'])


def record_to_event(record: asyncpg.Record) -> Dict:
    if record['end_time'] is not None:
        end = joule.utilities.datetime_to_timestamp(record['end_time'])
    else:
        end = None
    return {
        'id': record['id'],
        'start_time': joule.utilities.datetime_to_timestamp(record['start_time']),
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
