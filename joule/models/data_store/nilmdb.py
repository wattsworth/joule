import json
import aiohttp
from aiohttp import web
import asyncio
import re
import pdb
import numpy as np
from typing import List, Dict, Optional, Callable, Coroutine
from joule.models import Stream, pipes
from joule.models.data_store.data_store import DataStore, StreamInfo, Data, Interval
from joule.models.data_store import errors
from joule.models.data_store.nilmdb_inserter import Inserter
from joule.models.data_store.nilmdb_helpers import compute_path, check_for_error, ERRORS

Loop = asyncio.AbstractEventLoop


class PathNotFound(Exception):
    pass


class NilmdbStore(DataStore):

    def __init__(self, server: str, insert_period: float, cleanup_period: float, loop: Loop):
        self.server = server
        self.decimation_factor = 4
        self.insert_period = insert_period
        self.cleanup_period = cleanup_period
        self.connector = aiohttp.TCPConnector(loop=loop)
        self.loop = loop

    async def initialize(self, streams: List[Stream]) -> None:
        url = "{server}/stream/create".format(server=self.server)
        async with self._get_client() as session:
            for stream in streams:
                data = {"path": compute_path(stream),
                        "layout": stream.layout}
                async with session.post(url, data=data) as resp:
                    await check_for_error(resp, ignore=[ERRORS.STREAM_ALREADY_EXISTS])

    async def insert(self, stream: Stream, start: int, end: int, data: np.array) -> None:
        """insert stream data, retry on error"""
        url = "{server}/stream/insert".format(server=self.server)
        params = {"start": "%d" % start,
                  "end": "%d" % end,
                  "path": compute_path(stream),
                  "binary": '1'}
        async with self._get_client() as session:
            async with session.put(url, params=params,
                                   data=data.tostring()) as resp:
                if resp.status != 200:
                    if resp.status == 400:
                        error = await resp.json()
                        # nilmdb rejected the data
                        raise errors.DataError(error["message"])
                    raise Exception(resp)

    # TODO: change to accepting a DataPipe instead of a queue
    def spawn_inserter(self, stream: Stream,
                       pipe: pipes.InputPipe, loop: Loop) -> asyncio.Task:
        inserter = Inserter(self.server, stream,
                            self.insert_period, self.cleanup_period, self._get_client)
        return loop.create_task(inserter.run(pipe, loop))

    async def extract(self, stream: Stream, start: int, end: int,
                      callback: Callable[[np.ndarray], Coroutine], max_rows: int = None,
                      decimation_level=None) -> Coroutine:
        # figure out appropriate decimation level
        if decimation_level is None:
            if max_rows is None:
                decimation_level = 1
            else:
                # find out how much data this represents
                count = await self._count_by_path(compute_path(stream),
                                                  start, end)
                desired_decimation = np.ceil(count / max_rows)
                decimation_level = 4 ** np.ceil(np.log(desired_decimation) /
                                                np.log(self.decimation_factor))
                # make sure the target decimation level exists and has data
                try:
                    path = compute_path(stream, decimation_level)
                    if (await self._count_by_path(path, start, end)) == 0:
                        # no data in the decimated path
                        raise errors.InsufficientDecimationError("required level is empty")
                except errors.DataError as e:
                    if ERRORS.NO_SUCH_STREAM.value in str(e):
                        # no decimated data or required level does not exist
                        raise errors.InsufficientDecimationError("required level %d does not exist" % decimation_level)
                    raise e  # some other error, propogate it up
        elif max_rows is not None:
            # two constraints, make sure we aren't going to return too much data
            count = await self._count_by_path(compute_path(stream, decimation_level),
                                              start, end)
            if count > max_rows:
                raise errors.InsufficientDecimationError("actual_rows(%d) > max_rows(%d)" % (count, max_rows))

        # retrieve data from stream
        path = compute_path(stream, decimation_level)
        if decimation_level > 1:
            layout = stream.decimated_layout
        else:
            layout = stream.layout
        return self._extract_by_path(path, start, end, layout, callback)

    async def intervals(self, stream: Stream, start: Optional[int], end: Optional[int]):
        return await self._intervals_by_path(compute_path(stream),
                                             start, end)

    async def remove(self, stream, start, end):
        """ remove [start,end] in path and all decimations """
        info = await self._path_info()
        all_paths = info.keys()
        base_path = compute_path(stream)
        regex = re.compile("%s~decim-(\d)+$" % base_path)
        decim_paths = list(filter(regex.match, all_paths))
        for path in [base_path, *decim_paths]:
            await self._remove_by_path(path, start, end)

    async def info(self, stream: Stream) -> StreamInfo:
        path = compute_path(stream)
        info_dict = await self._path_info(path)
        return info_dict[path]

    async def _extract_by_path(self, path: str, start: Optional[int], end: Optional[int],
                               layout: str, callback):
        url = "{server}/stream/extract".format(server=self.server)
        params = {"path": path,
                  "binary": 1}
        decimated = False
        if re.search('~decim-(\d)+$', path):
            decimated = True
        async with self._get_client() as session:
            # first determine the intervals
            intervals = await self._intervals_by_path(path, start, end)
            # now extract each interval
            for interval in intervals:
                params["start"] = interval[0]
                params["end"] = interval[1]
                async with session.get(url, params=params) as resp:
                    await check_for_error(resp)
                    # put data into the queue as it arrives
                    reader = pipes.InputPipe(layout=layout, reader=resp.content)
                    while True:
                        try:
                            data = await reader.read()
                            await callback(data, layout, decimated)
                            reader.consume(len(data))
                        except pipes.EmptyPipe:
                            break
                await callback(pipes.interval_token(layout), layout, decimated)

    async def _intervals_by_path(self, path: str, start: Optional[int],
                                 end: Optional[int]) -> List[Interval]:
        url = "{server}/stream/intervals".format(server=self.server)
        params = {"path": path}
        if start is not None:
            params["start"] = start
        if end is not None:
            params["end"] = end
        intervals = []
        async with self._get_client() as session:
            async with session.get(url, params=params) as resp:
                await check_for_error(resp)
                text = await resp.text()
                if text == '':
                    return []
                for line in text.strip().split("\n"):
                    intervals.append(json.loads(line))
        return intervals

    async def _remove_by_path(self, path: str, start: Optional[int], end: Optional[int]):
        """remove data from streams"""
        url = "{server}/stream/remove".format(server=self.server)
        params = {"path": path}
        if start is not None:
            params["start"] = start
        if end is not None:
            params["end"] = end
        async with self._get_client() as session:
            async with session.post(url, params=params) as resp:
                await check_for_error(resp)
                await resp.text()  # wait for operation to complete

    async def _count_by_path(self, path, start: Optional[int], end: Optional[int]) -> int:
        url = "{server}/stream/extract".format(server=self.server)
        params = {"path": path,
                  "count": 1}
        if start is not None:
            params["start"] = start
        if end is not None:
            params["end"] = end
        async with self._get_client() as session:
            async with session.get(url, params=params) as resp:
                await check_for_error(resp)
                return int(await resp.text())

    async def _path_info(self, path=None) -> Dict[str, StreamInfo]:
        """ set path to None to list all streams """
        url = "{server}/stream/list".format(server=self.server)
        params = {"extended": 1}
        if path is not None:
            params["path"] = path
        async with self._get_client() as session:
            async with session.get(url, params=params) as resp:
                body = await resp.text()
                if resp.status != 200:
                    raise errors.DataError(body)
                data = json.loads(body)
                info = {}
                for item in data:
                    info[item[0]] = StreamInfo(start=item[2],
                                               end=item[3],
                                               rows=item[4])
                return info

    def _get_client(self):
        return aiohttp.ClientSession(connector=self.connector,
                                     loop=self.loop, connector_owner=False)

    def close(self):
        self.connector.close()
