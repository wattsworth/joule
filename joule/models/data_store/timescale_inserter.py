import asyncio
import numpy as np
import random
import time
import datetime
import logging
import asyncpg

from joule.models import Stream, pipes, stream
import joule.utilities
from joule.models.data_store import psql_helpers

Loop = asyncio.AbstractEventLoop
log = logging.getLogger('joule')


class Inserter:

    def __init__(self, conn: asyncpg.Connection, stream: Stream, insert_period: float,
                 cleanup_period: float):
        self.conn = conn
        self.stream = stream
        # round cleanup_period to a multiple of insert_period
        if insert_period == 0 or cleanup_period < insert_period:
            self.cleanup_interval = 1  # clean with every insert
        else:
            self.cleanup_interval = np.ceil(cleanup_period / insert_period)
        # add offsets to the period to distribute traffic
        self.insert_period = insert_period + insert_period * random.random() * 0.5
        self.decimator: Decimator = None

    async def run(self, pipe: pipes.Pipe) -> None:
        """insert stream data from the queue until the queue is empty"""

        # lazy stream creation
        try:
            await psql_helpers.create_stream_table(self.conn, self.stream)
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
                # there might be an interval break and no new data
                if len(data) > 0:
                    if first_insert:
                        first_insert = False
                        await psql_helpers.close_interval(self.conn, self.stream, data['timestamp'][0] - 1)
                    last_ts = data['timestamp'][-1]
                    # lazy initialization of decimator
                    if self.stream.decimate and self.decimator is None:
                        self.decimator = Decimator(self.stream, 1, 4)
                    psql_bytes = psql_helpers.data_to_bytes(data)
                    await self.conn.copy_to_table("stream%d" % self.stream.id,
                                                  schema_name='data',
                                                  format='binary',
                                                  source=psql_bytes)
                    # this was successful so consume the data
                    pipe.consume(len(data))
                    # decimate the data
                    if self.decimator is not None:
                        await self.decimator.process(self.conn, data)
                # check for interval breaks
                if pipe.end_of_interval and last_ts is not None:
                    await psql_helpers.close_interval(self.conn, self.stream, last_ts)
                ticks += 1
                if ticks % self.cleanup_interval == 0:
                    await self.cleanup()

        except (pipes.EmptyPipe, asyncio.CancelledError):
            pass
        await self.conn.close()

    async def cleanup(self):
        if self.stream.keep_us == Stream.KEEP_ALL:
            return
        tables = await psql_helpers.get_table_names(self.conn, self.stream, with_schema=False)
        # ts is milliseconds UNIX timestamp
        keep_s = self.stream.keep_us//1e6
        for table in tables:
            if 'interval' in table:
                # drop all boundaries before the cutoff
                cutoff = joule.utilities.timestamp_to_datetime(
                    joule.utilities.time_now() - self.stream.keep_us)
                query = "DELETE FROM data.%s WHERE time < '%s'" % (table, cutoff)
            else:
                query = "SELECT drop_chunks(interval '%d seconds', '%s', 'data')" % (keep_s, table)
            await self.conn.execute(query)


class Decimator:

    def __init__(self, stream: Stream, from_level: int, factor: int, debug=False):
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
        self.last_ts = None
        self.path_created = False
        self.child: Decimator = None
        self.debug = debug
        if self.debug:
            print("creating decim level %d" % self.level)
        # hold off to rate limit traffic
        self.holdoff = 0  # random.random()

    async def process(self, conn: asyncpg.Connection, data: np.ndarray) -> None:
        """decimate data and insert it, retry on error"""
        if not self.path_created:
            await psql_helpers.create_decimation_table(conn, self.stream, self.level)
            self.path_created = True

        decim_data = self._process(data)
        if self.debug:
            print("\t level %d: %d rows" % (self.level, len(decim_data)))
        if len(decim_data) == 0:
            return

        # lazy initialization of child
        if self.child is None:
            self.child = Decimator(self.stream, self.level, self.factor)

        psql_bytes = psql_helpers.data_to_bytes(decim_data)
        await conn.copy_to_table(self.table_name,
                                 schema_name='data',
                                 format='binary',
                                 source=psql_bytes)
        await self.child.process(conn, decim_data)

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
