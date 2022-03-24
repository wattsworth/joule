import asyncpg
import json

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
                serial = query[0]["stop"] - len(events)
                for e in new_events:
                    serial += 1
                    e["id"] = serial
                assert serial, query[0]["stop"]
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
                    start: Optional[int] = None, end: Optional[int] = None) -> int:
        if end is not None and start is not None and end <= start:
            raise ValueError("Invalid time bounds start [%d] must be < end [%d]" % (start, end))
        query = "SELECT count(*) FROM data.events "
        where_clause = psql_helpers.query_time_bounds(start, end)
        if len(where_clause) == 0:
            where_clause = "WHERE "
        else:
            where_clause += " AND "
        where_clause += "event_stream_id=%d" % stream.id
        query += where_clause
        async with self.pool.acquire() as conn:
            record = await conn.fetch(query)
            return record[0]['count']

    async def extract(self, stream: 'EventStream',
                      start: Optional[int] = None, end: Optional[int] = None) -> List[Dict]:
        if end is not None and start is not None and end <= start:
            raise ValueError("Invalid time bounds start [%d] must be < end [%d]" % (start, end))
        query = "SELECT id, time, end_time, content FROM data.events "
        where_clause = psql_helpers.query_time_bounds(start, end)
        if len(where_clause) == 0:
            where_clause = "WHERE "
        else:
            where_clause += " AND "
        where_clause += "event_stream_id=%d" % stream.id
        query += where_clause + " ORDER BY time ASC"
        async with self.pool.acquire() as conn:
            records = await conn.fetch(query)
            return list(map(record_to_event, records))

    async def remove(self, stream: 'EventStream', start: Optional[int] = None, end: Optional[int] = None):
        query = "DELETE FROM data.events "
        where_clause = psql_helpers.query_time_bounds(start, end)
        if len(where_clause) == 0:
            where_clause = "WHERE "
        else:
            where_clause += " AND "
        where_clause += "event_stream_id=%d" % stream.id
        query += where_clause
        async with self.pool.acquire() as conn:
            return await conn.execute(query)

    async def destroy(self, stream: 'EventStream'):
        await self.remove(stream)

    async def info(self, streams: List['EventStream']) -> Dict[int, 'StreamInfo']:
        results = {}
        async with self.pool.acquire() as conn:
            for my_stream in streams:
                rows = await conn.fetchval("SELECT COUNT(*) FROM data.events WHERE event_stream_id=%d" % my_stream.id)
                query = "SELECT time FROM data.events WHERE event_stream_id=%d ORDER BY time ASC LIMIT 1" % my_stream.id
                start_time = await conn.fetchval(query)
                if start_time is not None:
                    start_time = joule.utilities.datetime_to_timestamp(start_time)
                query = "SELECT time FROM data.events WHERE event_stream_id=%d ORDER BY time DESC LIMIT 1" % my_stream.id
                end_time = await conn.fetchval(query)
                if end_time is not None:
                    end_time = joule.utilities.datetime_to_timestamp(end_time)
                if start_time is not None:
                    total_time = end_time - start_time
                else:
                    total_time = 0
                total_bytes = 0  # TODO
                results[my_stream.id] = StreamInfo(start_time, end_time, rows, total_time, total_bytes)
        return results

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
        return "<DataStreamInfo start=%r end=%r event_count=%r, total_time=%r>" % (
            self.start, self.end, self.event_count, self.total_time)

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
