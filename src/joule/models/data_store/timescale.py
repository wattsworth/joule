import asyncio
from typing import List, Optional, Callable, Coroutine, Dict
import numpy as np
from io import BytesIO
import asyncpg
import asyncpg.exceptions
import datetime
import shutil
import asyncio
from joule.utilities import interval_tools, timestamp_to_datetime
from joule.models.data_store.timescale_inserter import Inserter, Decimator
from joule.models import DataStream, pipes
from joule.models.data_store import psql_helpers
from joule.models.data_store.data_store import DataStore, StreamInfo, DbInfo
from joule.utilities import datetime_to_timestamp as dt2ts
Loop = asyncio.AbstractEventLoop


class TimescaleStore(DataStore):

    def __init__(self, dsn: str, insert_period: float,
                 cleanup_period: float):
        self.dsn = dsn
        self.decimation_factor = 4
        self.insert_period = insert_period
        self.cleanup_period = cleanup_period
        self.pool = None
        # tunable constants
        self.extract_block_size = 50000

    async def initialize(self, streams: List[DataStream]) -> None:
        self.pool = await asyncpg.create_pool(self.dsn, command_timeout=60)
        return self.pool  # so the event store can reuse it

    async def close(self):
        try:
            await asyncio.wait_for(self.pool.close(), timeout=5.0)
        except asyncio.TimeoutError:
            print("WARNING: could not close timescale pool, terminating")

    async def spawn_inserter(self, stream: 'DataStream', pipe: pipes.Pipe, insert_period=None,
                             merge_gap=0) -> asyncio.Task:
        if insert_period is None:
            insert_period = self.insert_period

        inserter = Inserter(self.pool, stream,
                            insert_period=insert_period, 
                            cleanup_period=self.cleanup_period,
                            merge_gap=merge_gap)
        t = asyncio.create_task(inserter.run(pipe))
        t.set_name("Timescale Inserter for [%s]" % stream.name)
        return t

    async def insert(self, stream: 'DataStream',
                     data: np.ndarray, start: int, end: int):
        pass

    async def drop_decimations(self, stream: 'DataStream'):
        async with self.pool.acquire() as conn:
            await psql_helpers.drop_decimation_tables(conn, stream)

    async def decimate(self, stream: 'DataStream'):
        await self.drop_decimations(stream)
        async with self.pool.acquire() as conn:
            # do not change the chunk interval sizes
            decimator = Decimator(stream=stream, from_level=1, factor=4, chunk_interval=0)
            interval_token = pipes.interval_token(stream.layout)
            async def redecimator(data, _, __):
                if len(data)==0:
                    print("WARNING: decimator received a 0 length data array")
                    return
                # if the data is just an interval token, close the interval
                if len(data)==1 and data[0] == interval_token:
                    decimator.close_interval()
                    return
                # if the end of the data is an interval token, remove it
                if data[-1] == interval_token:
                    await decimator.process(conn, data[:-1])
                    decimator.close_interval()
                else: # normal data just process it
                    await decimator.process(conn, data)

            # start a data extraction task with the callback running
            # the decimation
            await _extract_data(conn, stream, redecimator,
                                decimation_level=1, start=None, end=None,
                                block_size=50000)

    async def consolidate(self, stream: 'DataStream', start: int,
                          end: int, max_gap: int) -> int:
        # remove interval gaps less than or equal to max_gap duration (in us)
        intervals = await self.intervals(stream, start, end)
        if len(intervals) == 0:
            return 0  # no data, nothing to do
        duration = [intervals[0][0], intervals[-1][1]]

        gaps = interval_tools.interval_difference([duration], intervals)

        if len(gaps) == 0:
            return 0  # no interval breaks, nothing to do
        small_gaps = [gap for gap in gaps if (gap[1] - gap[0]) <= max_gap]
        if len(small_gaps) == 0:
            return 0  # no small gaps, nothing to do
        boundaries = [gap[0] for gap in small_gaps]
        str_datetimes = ["'%s'" % str(timestamp_to_datetime(ts)) for ts in boundaries]
        query = "DELETE FROM data.stream%d_intervals WHERE time IN (%s)" % (stream.id, ",".join(str_datetimes))
        async with self.pool.acquire() as conn:
            await conn.execute(query)
        return len(small_gaps)

    async def intervals(self, stream: 'DataStream', start: Optional[int], end: Optional[int]):
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
                    utc_start_ts = round(cur_start.replace(tzinfo=datetime.timezone.utc).timestamp() * 1e6)
                    utc_end_ts = round(prev_ts.replace(tzinfo=datetime.timezone.utc).timestamp() * 1e6)
                    # intervals are [..) with extra us on the end
                    intervals.append([utc_start_ts, utc_end_ts + 1])
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

    async def extract(self, stream: 'DataStream', start: Optional[int], end: Optional[int],
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
                    # print("count=%d, max_rows=%d,desired_decim=%d,decim_level=%d" % (
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

    async def remove(self, stream: 'DataStream',
                     start: Optional[int], end: Optional[int],
                     exact: bool = True):
        where_clause = psql_helpers.query_time_bounds(start, end)
        if len(where_clause)>0:
            where_clause = " WHERE " + where_clause
        async with self.pool.acquire() as conn:
            tables = await psql_helpers.get_table_names(conn, stream)
            for table in tables:
                # TODO: use drop chunks with newer and older clauses when timescale is updated
                if start is None and end is None:
                    query = "TRUNCATE %s" % table
                elif start is None and "intervals" not in table and not exact:
                    # use the much faster drop chunks utility and accept the approximate result
                    bounds = await psql_helpers.convert_time_bounds(conn, stream, start, end)
                    if bounds is None:
                        return  # no data to remove
                    query = "SELECT drop_chunks('%s', older_than=>'%s'::timestamp)" % (table, bounds[1])
                else:
                    query = f'DELETE FROM {table} {where_clause}'
                try:
                    await conn.execute(query)
                except asyncpg.UndefinedTableError:
                    return  # no data to remove
                except asyncpg.exceptions.RaiseError as err:
                    print("psql: ", err)
                    return
            # create an interval boundary to mark the missing data
            if start is not None:
                await psql_helpers.close_interval(conn, stream, start)

    async def destroy(self, stream: 'DataStream'):
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

    async def info(self, streams: List['DataStream']) -> Dict[int, StreamInfo]:
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
                    start = round(start.replace(tzinfo=datetime.timezone.utc)
                                .timestamp() * 1e6)
                if end is not None:
                    end = round(end.replace(tzinfo=datetime.timezone.utc)
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
            try:
                usage = shutil.disk_usage(path)  # usage in bytes
                return DbInfo(path=path,
                              size=dbsize,
                              other=max(usage.used - dbsize, 0),
                              reserved=max(usage.total - usage.used - usage.free, 0),
                              free=usage.free)
            except FileNotFoundError:
                # this occurs if the database is remote
                return DbInfo(path="--remote-database--",
                              size=-1,
                              other=-1,
                              reserved=-1,
                              free=-1)


async def _extract_data(conn: asyncpg.Connection, stream: DataStream, callback,
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
    where_clause = psql_helpers.query_time_bounds(start, end)
    if len(where_clause)>0:
        query += " WHERE " + where_clause
    query += " ORDER BY time ASC"
    try:
        data = await conn.fetch(query)
        # convert to timestamps
        boundary_records = [dt2ts(row['time']) for row in data]
    except asyncpg.UndefinedTableError:
        # no data tables
        data = np.array([], dtype=pipes.compute_dtype(layout))
        await callback(data, layout, decimation_level)
        return

    boundary_records.append(end)
    for i in range(len(boundary_records)):
        end = boundary_records[i]
        # extract the interval data
        if start==end: # do not run an empty query
            continue
        done = False
        while not done:
            query = "SELECT * FROM %s " % table_name
            where_clause = psql_helpers.query_time_bounds(start, end)
            if len(where_clause)>0:
                query+= " WHERE " + where_clause
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

            if len(np_data) < block_size:
                # this is the last block in the interval, append an interval token
                # unless this is the end of the requested data
                if i < len(boundary_records) - 1:
                    # add an interval token to the end of np_data
                    np_data = np.append(np_data, pipes.interval_token(layout))
            if len(np_data)==0:
                print("WARNING: empty read, no data found in interval")
                break
                
            await callback(np_data, layout, decimation_level)

            if len(np_data) < block_size:
                break
            start = np_data['timestamp'][-1] + 1
        # do not put an interval token at the end of the data
        #if i < len(boundary_records) - 1:
        #    await callback(pipes.interval_token(layout), layout, decimation_level)
        start = end
