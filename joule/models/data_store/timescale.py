import asyncio
from typing import List, Optional, Callable, Coroutine, Dict
import numpy as np
from io import BytesIO
import asyncpg
import asyncpg.exceptions
import datetime
import shutil
import os

from joule.models.data_store.timescale_inserter import Inserter
from joule.models.data_store import psql_helpers
from joule.models import Stream, pipes
from joule.models.data_store.data_store import DataStore, StreamInfo, DbInfo

Loop = asyncio.AbstractEventLoop

SQL_DIR = os.path.join(os.path.dirname(__file__), 'sql')


class TimescaleStore(DataStore):

    def __init__(self, dsn: str, insert_period: float,
                 cleanup_period: float, loop: Loop):
        self.dsn = dsn
        self.decimation_factor = 4
        self.insert_period = insert_period
        self.cleanup_period = cleanup_period
        self.loop = loop
        self.pool = None
        # tunable constants
        self.extract_block_size = 50000

    async def initialize(self, streams: List[Stream]) -> None:
        conn: asyncpg.Connection = await asyncpg.connect(self.dsn)
        self.pool = await asyncpg.create_pool(self.dsn, command_timeout=60)
        # await conn.execute("CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;")
        await conn.execute("CREATE SCHEMA IF NOT EXISTS data")
        # load custom functions
        for file in os.listdir(SQL_DIR):
            file_path = os.path.join(SQL_DIR, file)
            with open(file_path, 'r') as f:
                await conn.execute(f.read())

        await conn.close()

    async def close(self):
        await self.pool.close()

    async def spawn_inserter(self, stream: 'Stream', pipe: pipes.Pipe,
                             loop: Loop, insert_period=None) -> asyncio.Task:
        if insert_period is None:
            insert_period = self.insert_period

        conn: asyncpg.Connection = await asyncpg.connect(self.dsn)

        inserter = Inserter(conn, stream,
                            insert_period, self.cleanup_period)
        return loop.create_task(inserter.run(pipe))

    async def insert(self, stream: 'Stream',
                     data: np.ndarray, start: int, end: int):
        pass

    async def intervals(self, stream: 'Stream', start: Optional[int], end: Optional[int]):
        # find the intervals
        # for each interval find the nearest data
        intervals = []
        async with self.pool.acquire() as conn:
            boundaries = await psql_helpers.get_boundaries(conn, stream, start, end)
            cur_start = None
            for i in range(len(boundaries)):
                boundary = boundaries[i]
                if cur_start is not None:
                    query = "SELECT time FROM data.stream%d WHERE time < '%s'" % (stream.id, boundary)
                    query += " ORDER BY time DESC LIMIT 1"
                    prev_ts = await conn.fetchval(query)
                    utc_start_ts = int(cur_start.replace(tzinfo=datetime.timezone.utc).timestamp() * 1e6)
                    utc_end_ts = int(prev_ts.replace(tzinfo=datetime.timezone.utc).timestamp() * 1e6)
                    intervals.append([utc_start_ts, utc_end_ts])
                    cur_start = None
                query = "SELECT time FROM data.stream%d WHERE time >= '%s'" % (stream.id, boundary)
                if i < (len(boundaries) - 1):
                    query += " AND time < '%s' " % (boundaries[i + 1])
                query += " ORDER BY time ASC LIMIT 1"
                next_ts = await conn.fetchval(query)
                if next_ts is None:
                    # unecessary interval marker, remove it?
                    continue
                if cur_start is None:
                    cur_start = next_ts
        return intervals

    async def extract(self, stream: 'Stream', start: Optional[int], end: Optional[int],
                      callback: Callable[[np.ndarray, str, int], Coroutine],
                      max_rows: int = None, decimation_level=None):
        conn = await self.pool.acquire()
        # limit time bounds to range of base stream
        (start, end) = await psql_helpers.limit_time_bounds(conn, stream, start, end)
        # figure out appropriate decimation level
        if decimation_level is None:
            if max_rows is None:
                decimation_level = 1
            else:
                # find out how much data this represents
                count = await psql_helpers.get_row_count(conn, stream, start, end)
                if count > 0:
                    desired_decimation = np.ceil(count / max_rows)

                    decimation_level = int(4 ** np.ceil(np.log(desired_decimation) /
                                                        np.log(self.decimation_factor)))
                    #print("count=%d, max_rows=%d,desired_decim=%d,decim_level=%d" % (
                    #    count, max_rows, desired_decimation, decimation_level))
                else:
                    # create an empty array with the right data type
                    data = np.array([], dtype=pipes.compute_dtype(stream.layout))
                    await callback(data, stream.layout, 1)
                    await self.pool.release(conn)
                    return
        try:
            await _extract_data(conn, stream, callback, decimation_level, start, end,
                                block_size=self.extract_block_size)
        except Exception as e:
            raise e
        finally:
            await self.pool.release(conn)

    async def remove(self, stream: 'Stream',
                     start: Optional[int], end: Optional[int],
                     exact: bool = True):
        where_clause = psql_helpers.query_time_bounds(start, end)
        async with self.pool.acquire() as conn:
            tables = await psql_helpers.get_table_names(conn, stream)
            for table in tables:
                # TODO: use drop chunks with newer and older clauses when timescale is updated
                # ******DROP CHUNKS IS *VERY* APPROXIMATE*********
                if start is None and "intervals" not in table and not exact:
                    # use the much faster drop chunks utility and accept the approximate result
                    bounds = await psql_helpers.convert_time_bounds(conn, stream, start, end)
                    if bounds is None:
                        return  # no data to remove
                    query = "SELECT drop_chunks(table_name=>'%s', schema_name=>'data', older_than=>'%s'::timestamp)" % \
                            (table.split(".")[1], bounds[1])
                else:
                    query = 'DELETE FROM %s ' % table + where_clause
                try:
                    await conn.execute(query)
                except asyncpg.UndefinedTableError:
                    return # no data to remove
                except asyncpg.exceptions.RaiseError as err:
                    print("psql: ", err)
                    return
            # create an interval boundary to mark the missing data
            if start is not None:
                await psql_helpers.close_interval(conn, stream, start)

    async def destroy(self, stream: 'Stream'):
        async with self.pool.acquire() as conn:
            tables = await psql_helpers.get_table_names(conn, stream)
            for table in tables:
                try:
                    await conn.execute('DROP TABLE %s ' % table)
                except asyncpg.UndefinedTableError:
                    pass

    async def destroy_all(self):
        async with self.pool.acquire() as conn:
            tables = await psql_helpers.get_all_table_names(conn)
            for table in tables:
                try:
                    await conn.execute('DROP TABLE %s ' % table)
                except asyncpg.UndefinedTableError:
                    pass

    async def info(self, streams: List['Stream']) -> Dict[int, StreamInfo]:
        results = {}
        async with self.pool.acquire() as conn:
            for my_stream in streams:
                try:
                    record = await conn.fetchrow("select * from stream_info(%d);" % my_stream.id)
                except asyncpg.UndefinedTableError:
                    # this stream has no data tables, just make up an empty record
                    record = {'min_ts': None, 'max_ts': None, 'rows': 0, 'size': 0}
                start = record['min_ts']
                end = record['max_ts']

                if start is not None:
                    start = int(start.replace(tzinfo=datetime.timezone.utc)
                                .timestamp() * 1e6)
                if end is not None:
                    end = int(end.replace(tzinfo=datetime.timezone.utc)
                              .timestamp() * 1e6)
                if start is not None and end is not None:
                    total_time = end - start
                else:
                    total_time = 0
                results[my_stream.id] = StreamInfo(start, end,
                                                   record['rows'],
                                                   total_time, record['size'])
        return results

    async def dbinfo(self) -> DbInfo:

        async with self.pool.acquire() as conn:
            dbsize = await conn.fetchval("select pg_database_size(current_database())")  # in bytes
            path = await conn.fetchval("show data_directory")
            usage = shutil.disk_usage(path)  # usage in bytes
            return DbInfo(path=path,
                          size=dbsize,
                          other=max(usage.used - dbsize, 0),
                          reserved=max(usage.total - usage.used - usage.free, 0),
                          free=usage.free)


async def _extract_data(conn: asyncpg.Connection, stream: Stream, callback,
                        decimation_level: int = 1, start: int = None, end: int = None,
                        block_size=50000):
    if decimation_level > 1:
        layout = stream.decimated_layout
    else:
        layout = stream.layout

    table_name = "data.stream%d" % stream.id
    if decimation_level > 1:
        table_name += "_%d" % decimation_level
    # extract by interval
    query = "SELECT time FROM data.stream%d_intervals " % stream.id
    query += psql_helpers.query_time_bounds(start, end)
    try:
        boundary_records = await conn.fetch(query)
    except asyncpg.UndefinedTableError:
        # no data tables
        data = np.array([], dtype=pipes.compute_dtype(layout))
        await callback(data, layout, decimation_level)
        return

    boundary_records += [{'time': end}]
    for i in range(len(boundary_records)):
        record = boundary_records[i]
        end = record['time']
        # extract the interval data
        done = False
        while not done:
            query = "SELECT * FROM %s " % table_name
            query += psql_helpers.query_time_bounds(start, end)
            query += " ORDER BY time ASC LIMIT %d" % block_size
            psql_bytes = BytesIO()
            try:
                await conn.copy_from_query(query, format='binary', output=psql_bytes)
            except asyncpg.UndefinedTableError:
                # interval table exists but not the data table
                data = np.array([], dtype=pipes.compute_dtype(layout))
                await callback(data, layout, decimation_level)
                return
            psql_bytes.seek(0)
            dtype = pipes.compute_dtype(layout)
            np_data = psql_helpers.bytes_to_data(psql_bytes, dtype)
            await callback(np_data, layout, decimation_level)

            if len(np_data) < block_size:
                break
            start = np_data['timestamp'][-1] + 1
        # do not put an interval token at the end of the data
        if i < len(boundary_records) - 1:
            await callback(pipes.interval_token(layout), layout, decimation_level)
        start = end
