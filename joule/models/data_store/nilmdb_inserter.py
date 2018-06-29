import asyncio
import aiohttp
import numpy as np
import random
import time
from typing import List, Callable
import pdb

from joule.models import Stream, pipes
from joule.models.data_store import errors
from joule.models.data_store.nilmdb_helpers import compute_path, ERRORS, check_for_error

Loop = asyncio.AbstractEventLoop


class Inserter:

    def __init__(self, server: str, stream: Stream, insert_period: float, cleanup_period: float,
                 session_factory: Callable[[], aiohttp.ClientSession]):
        self.insert_url = "{server}/stream/insert".format(server=server)
        self.remove_url = "{server}/stream/remove".format(server=server)
        self.create_url = "{server}/stream/create".format(server=server)

        self.server = server  # save for initializing decimators
        self.stream = stream
        self.path = compute_path(stream)
        self.decimator: NilmdbDecimator = None
        self.last_ts = None
        # add offsets to the period to distribute traffic
        self.insert_period = insert_period + insert_period*random.random()*0.5
        self.cleanup_period = cleanup_period + cleanup_period*random.random()*0.25
        self._get_client = session_factory

    async def run(self, pipe: pipes.InputPipe, loop: Loop) -> None:
        """insert stream data from the queue until the queue is empty"""
        decimator_queue = asyncio.Queue()
        decimator_task: asyncio.Task = None
        cleaner_task: asyncio.Task = None
        # create the database path
        # lazy stream creation
        await self._create_path()
        if self.stream.keep_us != Stream.KEEP_ALL:
            cleaner_task = loop.create_task(self._clean())
        try:
            async with self._get_client() as session:
                last_ts = None
                while True:
                    await asyncio.sleep(self.insert_period)
                    data = await pipe.read()
                    if last_ts is not None:
                        start = last_ts
                    else:
                        start = data['timestamp'][0]
                    end = data['timestamp'][-1] + 1
                    last_ts = end
                    if pipe.end_of_interval:
                        self.last_ts = None
                        if self.decimator is not None:
                            self.decimator.close_interval()
                    # lazy initialization of decimator
                    if self.stream.decimate and self.decimator is None:
                        self.decimator = NilmdbDecimator(self.server, self.stream, 1, 4,
                                                         self._get_client)
                        decimator_task = loop.create_task(self.decimator.run(decimator_queue, loop))
                    # send the data
                    params = {"start": "%d" % start,
                              "end": "%d" % end,
                              "path": self.path,
                              "binary": '1'}
                    async with session.put(self.insert_url, params=params,
                                           data=data.tostring()) as resp:
                        if resp.status != 200:
                            error = await resp.text()
                            raise errors.DataError("NilmDB error: %s" % error)
                    await decimator_queue.put(data)
        except asyncio.CancelledError:
            pass
        except pipes.EmptyPipe:
            pass
        if decimator_task is not None:
            decimator_task.cancel()
            await decimator_task
        if cleaner_task is not None:
            cleaner_task.cancel()
            await cleaner_task

    async def _process(self, queue: asyncio.Queue) -> (int, int, np.array):
        buffer = []
        start = None
        end = None
        while not queue.empty():
            data = await queue.get()
            if data is None:
                return 0, 0, None  # indicates a break in the data
            if len(buffer) == 0:
                buffer = np.array(data)
            else:
                buffer = np.append(buffer, data, axis=0)
            if self.last_ts is not None:
                start = self.last_ts
            else:
                start = buffer['timestamp'][0]
            end = buffer['timestamp'][-1]+1
            self.last_ts = end
        return start, end, buffer

    async def _close_interval(self):
        self.last_ts = 0
        if self.decimator is not None:
            self.decimator.close_interval()

    async def _create_path(self):
        data = {"path": compute_path(self.stream),
                "layout": self.stream.layout}
        async with self._get_client() as session:
            async with session.post(self.create_url, data=data) as resp:
                await check_for_error(resp, ignore=[ERRORS.STREAM_ALREADY_EXISTS])

    async def _clean(self):
        try:
            async with aiohttp.ClientSession() as session:
                while True:
                    await asyncio.sleep(self.cleanup_period)
                    keep_time = int(time.time()*1e6) - self.stream.keep_us
                    # remove raw data
                    params = {"start": "%d" % 0,
                              "end": "%d" % keep_time,
                              "path": self.path}
                    async with session.post(self.remove_url, params=params) as resp:
                        if resp.status != 200:
                            raise errors.DataError(await resp.text())
                    # remove decimation data
                    if self.decimator is not None:
                        for path in self.decimator.get_paths():
                            params["path"] = path
                            async with session.post(self.remove_url, params=params) as resp:
                                if resp.status != 200:
                                    raise errors.DataError(await resp.text())

        except asyncio.CancelledError:
            pass


class NilmdbDecimator:

    def __init__(self, server: str, stream: Stream, from_level: int, factor: int,
                 session_factory: Callable[[], aiohttp.ClientSession]):
        self.stream = stream
        self.level = from_level*factor
        self.insert_url = "{server}/stream/insert".format(server=server)
        self.create_url = "{server}/stream/create".format(server=server)
        self.server = server
        self.path = compute_path(stream, self.level)
        if from_level > 1:
            self.again = True
        else:
            self.again = False
        self.factor = factor
        self.layout = stream.decimated_layout
        self.buffer = []
        self.last_ts = None
        self.child: NilmdbDecimator = None
        self._get_client = session_factory
        # hold off to rate limit NilmDB traffic
        self.holdoff = 0 #random.random()

    async def run(self, queue: asyncio.Queue, loop: Loop) -> None:
        """insert stream data from the queue until the queue is empty"""
        await self._create_path()
        child_queue = asyncio.Queue()
        child_task: asyncio.Task = None
        try:
            async with self._get_client() as session:
                while True:
                    data = await queue.get()
                    (start, end, decim_data) = self._process(data)
                    if len(decim_data) == 0:
                        continue
                    # lazy initialization of child
                    if self.child is None:
                        self.child = NilmdbDecimator(self.server, self.stream, self.level,
                                                     self.factor, self._get_client)
                        child_task = loop.create_task(self.child.run(child_queue, loop))
                    params = {"start": "%d" % start,
                              "end": "%d" % end,
                              "path": self.path,
                              "binary": '1'}
                    async with session.put(self.insert_url, params=params,
                                           data=decim_data.tostring()) as resp:
                        if resp.status != 200:
                            error = await resp.text()
                            raise errors.DataError("NilmDB error: %s" % error)
                    # feed data to child decimator
                    await child_queue.put(decim_data)
                    await asyncio.sleep(self.holdoff)
        except asyncio.CancelledError:
            pass
        if child_task is not None:
            child_task.cancel()
            await child_task

    def close_interval(self):
        self.buffer = []
        self.last_ts = None
        if self.child is not None:
            self.child.close_interval()

    def get_paths(self) -> List[str]:
        paths = [compute_path(self.stream, self.level)]
        if self.child is not None:
            paths = paths + self.child.get_paths()
        return paths

    def _process(self, sarray: np.array) -> (int, int, np.array):

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
            return None, None, []

        trunc_data = data[:n, :]
        # keep the leftover data
        self.buffer = np.copy(data[n:, :])

        # Reshape it into 3D so we can process 'factor' rows at a time
        trunc_data = trunc_data.reshape(n // self.factor, self.factor, m)

        # Fill the result
        out = np.c_[np.mean(trunc_data[:, :, mean_col], axis=1),
                    np.min(trunc_data[:, :, min_col], axis=1),
                    np.max(trunc_data[:, :, max_col], axis=1)]

        # set up the interval
        if self.last_ts is None:
            self.last_ts = data[0, 0]

        start = self.last_ts
        end = data[n - 1, 0] + 1
        self.last_ts = end

        # structure the array
        width = np.shape(out)[1] - 1
        dtype = np.dtype([('timestamp', '<i8'), ('data', '<f4', width)])
        sout = np.zeros(out.shape[0], dtype=dtype)
        sout['timestamp'] = out[:, 0]
        sout['data'] = out[:, 1:]
        # insert the data into the database
        return start, end, sout

    async def _create_path(self):
        data = {"path": compute_path(self.stream, self.level),
                "layout": self.stream.decimated_layout}
        async with self._get_client() as session:
            async with session.post(self.create_url, data=data) as resp:
                await check_for_error(resp, ignore=[ERRORS.STREAM_ALREADY_EXISTS])


