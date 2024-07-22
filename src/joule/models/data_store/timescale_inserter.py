import asyncio
import numpy as np
import random
import logging
import asyncpg
import socket
import psutil

from joule.models import DataStream, pipes
from joule.models.data_store import psql_helpers
from joule.models.data_store.errors import DataError
import joule.utilities

Loop = asyncio.AbstractEventLoop
log = logging.getLogger('joule')
MAX_CHUNK_INTERVAL = 1000 * 1000 * 60 * 60 * 24 * 365 # 1 year in microseconds


class Inserter:

    def __init__(self, pool: asyncpg.pool.Pool, stream: DataStream, insert_period: float,
                 cleanup_period: float, merge_gap: int=0):
        self.pool = pool
        self.stream = stream
        self._data_rate_buffer = []
        # TODO: make this configurable, right now it is computed automatically
        self._chunk_interval = 0  # duration in seconds, 0 means not set
        # round cleanup_period to a multiple of insert_period
        if insert_period == 0 or cleanup_period < insert_period:
            self.cleanup_interval = 1  # clean with every insert
        else:
            self.cleanup_interval = np.ceil(cleanup_period / insert_period)
        # add offsets to the period to distribute traffic
        self.insert_period = insert_period + insert_period * random.random() * 0.5
        self.decimator: Decimator = None
        # merge this insertion with the previous data if the timestamps are <= merge_gap us appart
        self.merge_gap = merge_gap

    async def run(self, pipe: pipes.Pipe) -> None:
        """insert stream data from the queue until the queue is empty"""

        # lazy stream creation
        try:
            async with self.pool.acquire() as conn:
                await psql_helpers.create_stream_table(conn, self.stream)
        except asyncio.CancelledError:
            return

        # close the beginning of the data insert
        first_insert = True
        # track the last timestamp inserted
        last_ts = None
        ticks = 0
        try:
            while True:
                await asyncio.sleep(self.insert_period)
                data = await pipe.read()
                await self._measure_data_rate(data)
                try:
                    async with self.pool.acquire() as conn:
                        # there might be an interval break and no new data
                        if len(data) > 0:
                            if first_insert:
                                first_insert = False
                                await psql_helpers.close_interval(conn, self.stream, data['timestamp'][0] - 1)
                                # if the difference between the current data and this new data
                                # is less than merge_gap apart remove the interval boundary
                                if self.merge_gap > 0:
                                    await psql_helpers.remove_interval_breaks(conn, self.stream, 
                                                                              start=data['timestamp'][0]-self.merge_gap,
                                                                              end=data['timestamp'][0])
                                #closest_ts = await psql_helpers.get_closest_ts(conn, self.stream, data['timestamp'][0])
                                #if closest_ts is not None and data['timestamp'][0] - closest_ts > self.merge_gap:
                                #    await psql_helpers.close_interval(conn, self.stream, data['timestamp'][0] - 1)
                                #    print("closing interval with previous data")
                                #elif closest_ts is None:
                                #    print("no earlier ts in data")
                                #else:
                                #    print(f"merging new data with pervious interval: {data['timestamp'][0] - closest_ts} <= {self.merge_gap}")
                                #    print(f"TODO: remove any previous intervals")
                            if not joule.utilities.misc.timestamps_are_monotonic(data, last_ts, self.stream.name):
                                raise DataError("Non-monotonic timestamps in new data")
                            if not joule.utilities.misc.validate_values(data):
                                raise DataError("Invalid values (NaN) in new data")
                            last_ts = data['timestamp'][-1]
                            # lazy initialization of decimator
                            if self.stream.decimate and self.decimator is None:
                                self.decimator = Decimator(self.stream, 1, 4, self._chunk_interval)
                            psql_bytes = psql_helpers.data_to_bytes(data)
                            try:
                                await conn.copy_to_table("stream%d" % self.stream.id,
                                                         schema_name='data',
                                                         format='binary',
                                                         source=psql_bytes)
                                #print("-----BEGIN-------")
                                #print(f"wrote {data['timestamp']} timestamps to stream{self.stream.id}")
                                #display the byteio object as a hex string
                                #print(psql_helpers.data_to_bytes(data).getvalue().hex())
                                #print("-------END-----")
                            except asyncpg.exceptions.UniqueViolationError as e:
                                raise DataError(e)

                            # this was successful so consume the data
                            pipe.consume(len(data))
                            # decimate the data
                            if self.decimator is not None:
                                await self.decimator.process(conn, data)
                        # check for interval breaks
                        if pipe.end_of_interval and last_ts is not None:
                            await psql_helpers.close_interval(conn, self.stream, last_ts)
                            if self.decimator is not None:
                                self.decimator.close_interval()
                        ticks += 1
                        if ticks % self.cleanup_interval == 0:
                            await self.cleanup(conn)
                except (asyncpg.exceptions.PostgresConnectionError, socket.error) as e:
                    log.error(f"Timescale inserter: [{str(e)}, trying again in 2 seconds")
                    await asyncio.sleep(2)

        except (pipes.EmptyPipe, asyncio.CancelledError):
            pass

    async def cleanup(self, conn: asyncpg.Connection):
        if self.stream.keep_us == DataStream.KEEP_ALL:
            return
        tables = await psql_helpers.get_table_names(conn, self.stream, with_schema=False)
        # ts is milliseconds UNIX timestamp
        keep_s = self.stream.keep_us // 1e6
        for table in tables:
            if 'interval' in table:
                # drop all boundaries before the cutoff
                cutoff = joule.utilities.timestamp_to_datetime(
                    joule.utilities.time_now() - self.stream.keep_us)
                query = "DELETE FROM data.%s WHERE time < '%s'" % (table, cutoff)
            else:
                query = "SELECT drop_chunks('data.%s',older_than => interval '%d seconds')" % (table, keep_s)
            await conn.execute(query)

    async def update_chunk_interval(self, chunk_interval: int) -> None:
        self._chunk_interval = min(chunk_interval, MAX_CHUNK_INTERVAL)
        async with self.pool.acquire() as conn:
            await psql_helpers.update_chunk_interval(conn, f"data.stream{self.stream.id}",
                                                     self._chunk_interval)
            if self.decimator is not None:
                await self.decimator.update_chunk_interval(conn, self._chunk_interval)

    async def _measure_data_rate(self, data: np.ndarray) -> None:
        if self._chunk_interval != 0:
            return  # already measured
        self._data_rate_buffer += (data['timestamp']).tolist()
        if len(self._data_rate_buffer) < 200:
            return  # not enough data
        # determine the data rate by using the median of the differences
        # between timestamps
        diffs = np.diff(self._data_rate_buffer)
        data_rate = 1e6 / np.median(diffs) * data.dtype.itemsize
        total_memory = psutil.virtual_memory().total
        # set chunk size to 5% of available memory, this allows ~5 active streams
        self._chunk_interval = (int(total_memory * 0.05) / data_rate)*1e6 # in microseconds
        hours = self._chunk_interval / (1e6*60*60)
        memory = int(total_memory*0.05)/1e6
        #print(f"setting target chunk interval for {self.stream.name} [{self.stream.id}] to {hours}  ~ {memory}MB")
        #print(f"Data rate: {data_rate} bytes/sec, chunk interval: {self._chunk_interval} ms")
        await self.update_chunk_interval(self._chunk_interval)


class Decimator:

    def __init__(self, stream: DataStream, from_level: int, factor: int,
                 chunk_interval: int, debug=False):
        self.stream = stream
        self.level = from_level * factor
        self.table_name = "stream%d_%d" % (stream.id, self.level)
        self.full_table_name = "data." + self.table_name
        if from_level > 1:
            self.again = True
        else:
            self.again = False
        self.factor = factor
        self.layout = stream.decimated_layout
        self.buffer = []
        self.path_created = False
        self.chunk_interval = min(chunk_interval, MAX_CHUNK_INTERVAL)
        self.child: Decimator = None
        self.debug = debug
        if self.debug:
            print("creating decim level %d" % self.level)
        # hold off to rate limit traffic
        self.holdoff = 0  # random.random()

    async def update_chunk_interval(self, conn: asyncpg.Connection, chunk_interval):
        self.chunk_interval = min(chunk_interval, MAX_CHUNK_INTERVAL)
        await psql_helpers.update_chunk_interval(conn, self.full_table_name, self.chunk_interval)
        if self.child is not None:
            await self.child.update_chunk_interval(conn, self.chunk_interval * 4)

    async def process(self, conn: asyncpg.Connection, data: np.ndarray) -> None:
        """decimate data and insert it, retry on error"""
        if not self.path_created:
            await psql_helpers.create_decimation_table(conn, self.stream, self.level)
            if self.chunk_interval > 0:
                await psql_helpers.update_chunk_interval(conn, self.full_table_name, self.chunk_interval)
            self.path_created = True

        decim_data = self._process(data)
        if self.debug:
            print("\t level %d: %d rows" % (self.level, len(decim_data)))
        if len(decim_data) == 0:
            return

        # lazy initialization of child
        if self.child is None:
            self.child = Decimator(self.stream, self.level, self.factor,
                                   self.chunk_interval * 4, self.debug)

        psql_bytes = psql_helpers.data_to_bytes(decim_data)
        await conn.copy_to_table(self.table_name,
                                 schema_name='data',
                                 format='binary',
                                 source=psql_bytes)
        await self.child.process(conn, decim_data)

    def close_interval(self):
        self.buffer = []
        if self.child is not None:
            self.child.close_interval()

    def _process(self, sarray: np.ndarray) -> np.ndarray:

        # flatten structured array
        data = np.c_[sarray['timestamp'][:, None], sarray['data']]

        # check if there is old data
        if len(self.buffer) != 0:
            # append the new data onto the old data
            data = np.concatenate((self.buffer, data))
        (n, m) = data.shape

        # Figure out which columns to use as the input for mean, min, and max,
        # depending on whether this is the first decimation or we're decimating
        # again.  Note that we include the timestamp in the means.
        if self.again:
            c = (m - 1) // 3
            # e.g. c = 3
            # ts mean1 mean2 mean3 min1 min2 min3 max1 max2 max3
            mean_col = slice(0, c + 1)
            min_col = slice(c + 1, 2 * c + 1)
            max_col = slice(2 * c + 1, 3 * c + 1)
        else:
            mean_col = slice(0, m)
            min_col = slice(1, m)
            max_col = slice(1, m)

        # Discard extra rows that aren't a multiple of factor
        n = n // self.factor * self.factor

        if n == 0:  # not enough data to work with, save it for later
            self.buffer = data
            return np.array([])

        trunc_data = data[:n, :]
        # keep the leftover data
        self.buffer = np.copy(data[n:, :])

        # Reshape it into 3D so we can process 'factor' rows at a time
        trunc_data = trunc_data.reshape(n // self.factor, self.factor, m)

        # Fill the result
        out = np.c_[np.mean(trunc_data[:, :, mean_col], axis=1),
                    np.min(trunc_data[:, :, min_col], axis=1),
                    np.max(trunc_data[:, :, max_col], axis=1)]

        # structure the array
        width = np.shape(out)[1] - 1
        dtype = np.dtype([('timestamp', '<i8'), ('data', '<f4', width)])
        sout = np.zeros(out.shape[0], dtype=dtype)
        sout['timestamp'] = out[:, 0]
        sout['data'] = out[:, 1:]
        # insert the data into the database
        return sout
