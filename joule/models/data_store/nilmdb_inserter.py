import asyncio
import aiohttp
import numpy as np
import random
import time
from typing import List, Callable
import logging

from joule.models import Stream, pipes
from joule.models.data_store import errors
from joule.models.data_store.nilmdb_helpers import compute_path, ERRORS, check_for_error

Loop = asyncio.AbstractEventLoop
log = logging.getLogger('joule')


class Inserter:

    def __init__(self, server: str, stream: Stream, insert_period: float, cleanup_period: float,
                 session_factory: Callable[[], aiohttp.ClientSession], retry_interval=0.5):
        self.insert_url = "{server}/stream/insert".format(server=server)
        self.remove_url = "{server}/stream/remove".format(server=server)
        self.create_url = "{server}/stream/create".format(server=server)

        self.server = server  # save for initializing decimators
        self.stream = stream
        self.path = compute_path(stream)
        # add offsets to the period to distribute traffic
        self.insert_period = insert_period + insert_period * random.random() * 0.5
        self.cleanup_period = cleanup_period + cleanup_period * random.random() * 0.25
        self._get_client = session_factory
        self.decimator = None
        self.retry_interval = retry_interval

    async def run(self, pipe: pipes.Pipe, loop: Loop) -> None:
        """insert stream data from the queue until the queue is empty"""
        # create the database path
        # lazy stream creation,
        try:
            await self._create_path()
        except asyncio.CancelledError:
            return

        cleaner_task: asyncio.Task = None
        if self.stream.keep_us != Stream.KEEP_ALL:
            cleaner_task = loop.create_task(self._clean())

        while True:
            try:
                async with self._get_client() as session:
                    last_ts = None
                    while True:
                        await asyncio.sleep(self.insert_period)
                        data = await pipe.read()
                        # there might be an interval break and no new data
                        if len(data) > 0:
                            if last_ts is not None:
                                start = last_ts
                            else:
                                start = data['timestamp'][0]
                            end = data['timestamp'][-1] + 1
                            last_ts = end
                            # lazy initialization of decimator
                            if self.stream.decimate and self.decimator is None:
                                self.decimator = NilmdbDecimator(self.server, self.stream, 1, 4,
                                                                 self._get_client)
                            # send the data
                            params = {"start": "%d" % start,
                                      "end": "%d" % end,
                                      "path": self.path,
                                      "binary": '1'}
                            async with session.put(self.insert_url, params=params,
                                                   data=data.tostring()) as resp:
                                if resp.status != 200:
                                    error = await resp.text()
                                    if cleaner_task is not None:
                                        cleaner_task.cancel()
                                        await cleaner_task
                                    raise errors.DataError("NilmDB error: %s" % error)
                            # this was successful so consume the data
                            pipe.consume(len(data))
                            # decimate the data
                            if self.decimator is not None:
                                await self.decimator.process(data)
                        # check for interval breaks
                        if pipe.end_of_interval:
                            last_ts = None
                            if self.decimator is not None:
                                self.decimator.close_interval()
            except aiohttp.ClientError as e:  # pragma: no cover
                log.warning("NilmDB raw inserter error: %r, retrying request" % e)
                await asyncio.sleep(self.retry_interval)  # retry the request
            except (pipes.EmptyPipe, asyncio.CancelledError):
                break  # terminate the inserter
        if cleaner_task is not None:
            cleaner_task.cancel()
            await cleaner_task

    async def _create_path(self):
        data = {"path": compute_path(self.stream),
                "layout": self.stream.layout}
        while True:
            try:
                async with self._get_client() as session:
                    async with session.post(self.create_url, data=data) as resp:
                        await check_for_error(resp, ignore=[ERRORS.STREAM_ALREADY_EXISTS])
                        break
            except aiohttp.ClientError as e:  # pragma: no cover
                log.warning("NilmDB inserter create_path error: %r, retrying request" % e)
                await asyncio.sleep(self.retry_interval)  # retry the request

    async def _clean(self):
        while True:
            try:
                async with self._get_client() as session:
                    while True:
                        await asyncio.sleep(self.cleanup_period)
                        keep_time = int(time.time() * 1e6) - self.stream.keep_us
                        # remove raw data
                        params = {"start": "%d" % 0,
                                  "end": "%d" % keep_time,
                                  "path": self.path}
                        async with session.post(self.remove_url, params=params) as resp:
                            if resp.status != 200:  # pragma: no cover
                                msg = await resp.text()
                                log.error("NilmDB cleaning error: %s" % msg)
                        # remove decimation data
                        if self.decimator is not None:
                            for path in self.decimator.get_paths():
                                params["path"] = path
                                async with session.post(self.remove_url, params=params) as resp:
                                    if resp.status != 200:  # pragma: no cover
                                        msg = await resp.text()
                                        log.error("NilmDB cleaning error: %s" % msg)
            except aiohttp.ClientError as e:  # pragma: no cover
                log.warning("NilmDB cleaning error: %r" % e)
            except asyncio.CancelledError:
                break


class NilmdbDecimator:

    def __init__(self, server: str, stream: Stream, from_level: int, factor: int,
                 session_factory: Callable[[], aiohttp.ClientSession], retry_interval=0.5):
        self.stream = stream
        self.level = from_level * factor
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
        self.path_created = False
        self.child: NilmdbDecimator = None
        self.retry_interval = retry_interval
        self._get_client = session_factory
        # hold off to rate limit NilmDB traffic
        self.holdoff = 0  # random.random()

    async def process(self, data: np.ndarray) -> None:
        """decimate data and insert it, retry on error"""
        while True:
            try:
                if not self.path_created:
                    await self._create_path()
                    self.path_created = True

                async with self._get_client() as session:
                    decim_data = self._process(data)
                    if len(decim_data) == 0:
                        return
                    if self.last_ts is not None:
                        start = self.last_ts
                    else:
                        start = decim_data['timestamp'][0]
                    end = decim_data['timestamp'][-1] + 1
                    self.last_ts = end
                    # lazy initialization of child
                    if self.child is None:
                        self.child = NilmdbDecimator(self.server, self.stream, self.level,
                                                     self.factor, self._get_client)
                    params = {"start": "%d" % start,
                              "end": "%d" % end,
                              "path": self.path,
                              "binary": '1'}
                    async with session.put(self.insert_url, params=params,
                                           data=decim_data.tostring()) as resp:
                        if resp.status != 200:  # pragma: no cover
                            error = await resp.text()
                            raise errors.DataError("NilmDB(d) error: %s" % error)
                    # feed data to child decimator
                    await self.child.process(decim_data)
                    await asyncio.sleep(self.holdoff)
                    break  # success, leave the loop
            except aiohttp.ClientError as e:  # pragma: no cover
                log.warning("NilmDB decimation error: %r, retrying request" % e)
                await asyncio.sleep(self.retry_interval)  # retry the request
            except asyncio.CancelledError:  # pragma: no cover
                break

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

    async def _create_path(self):
        data = {"path": compute_path(self.stream, self.level),
                "layout": self.stream.decimated_layout}
        while True:
            try:
                async with self._get_client() as session:
                    async with session.post(self.create_url, data=data) as resp:
                        await check_for_error(resp, ignore=[ERRORS.STREAM_ALREADY_EXISTS])
                        break
            except aiohttp.ClientError as e:  # pragma: no cover
                log.warning("NilmDB decimator create_path error: %r, retrying request" % e)
                await asyncio.sleep(self.retry_interval)  # retry the request
