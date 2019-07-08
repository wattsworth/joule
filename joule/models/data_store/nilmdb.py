import json
import aiohttp
from aiohttp import web
import asyncio
import re
import numpy as np
from typing import List, Dict, Optional, Callable, Coroutine
from joule.models import Stream, pipes
from joule.models.data_store.data_store import DataStore, StreamInfo, DbInfo, Interval
from joule.models.data_store import errors
from joule.models.data_store.nilmdb_inserter import Inserter
from joule.models.data_store.nilmdb_helpers import (compute_path,
                                                    check_for_error,
                                                    ERRORS)

Loop = asyncio.AbstractEventLoop


class PathNotFound(Exception):
    pass


class NilmdbStore(DataStore):

    def __init__(self, server: str, insert_period: float, cleanup_period: float, loop: Loop):
        self.server = server
        self.decimation_factor = 4
        self.insert_period = insert_period
        self.cleanup_period = cleanup_period
        self.loop = loop
        self.connector = None

    async def initialize(self, streams: List[Stream]) -> None:
        self.connector = aiohttp.TCPConnector(loop=self.loop)
        url = "{server}/stream/create".format(server=self.server)
        try:
            async with self._get_client() as session:
                for stream in streams:
                    data = {"path": compute_path(stream),
                            "layout": stream.layout}
                    async with session.post(url, data=data) as resp:
                        await check_for_error(resp, ignore=[ERRORS.STREAM_ALREADY_EXISTS])
        except aiohttp.ClientError:
            raise errors.DataError("cannot contact NilmDB at [%s]" % self.server)

    async def insert(self, stream: Stream, start: int, end: int, data: np.array) -> None:
        """insert stream data"""
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
                    raise errors.DataError(await resp.text())  # pragma: no cover

    async def spawn_inserter(self, stream: Stream,
                             pipe: pipes.Pipe, loop: Loop, insert_period=None, retry_interval=0.5) -> asyncio.Task:
        if insert_period is None:
            insert_period = self.insert_period
        inserter = Inserter(self.server, stream,
                            insert_period, self.cleanup_period, self._get_client,
                            retry_interval=retry_interval)
        return loop.create_task(inserter.run(pipe, loop))

    async def extract(self, stream: Stream, start: Optional[int], end: Optional[int],
                      callback: Callable[[np.ndarray, str, int], Coroutine], max_rows: int = None,
                      decimation_level=None):
        # figure out appropriate decimation level
        if decimation_level is None:
            if max_rows is None:
                decimation_level = 1
            else:
                # find out how much data this represents
                count = await self._count_by_path(compute_path(stream),
                                                  start, end)
                if count > 0:
                    desired_decimation = np.ceil(count / max_rows)
                    decimation_level = 4 ** np.ceil(np.log(desired_decimation) /
                                                    np.log(self.decimation_factor))
                else:
                    # create an empty array with the right data type
                    data = np.array([], dtype=pipes.compute_dtype(stream.layout))
                    await callback(data, stream.layout, 1)
                    return
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
                    # some other error, propogate it up
                    raise e  # pragma: no cover
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
        try:
            await self._extract_by_path(path, start, end, layout, callback)
        except aiohttp.ClientError as e:
            raise errors.DataError(str(e))

    async def intervals(self, stream: Stream, start: Optional[int], end: Optional[int]):
        try:
            return await self._intervals_by_path(compute_path(stream),
                                                 start, end)
        except errors.DataError as e:
            # if the stream hasn't been written to it won't exist in the database
            if ERRORS.NO_SUCH_STREAM.value in str(e):
                return []
            else:
                raise e

    # TODO: remove path lookup, iterate until the stream decimation isn't found
    async def remove(self, stream, start: Optional[int] = None,
                     end: Optional[int] = None):
        """ remove [start,end] in path and all decimations """
        info = await self._path_info()
        all_paths = info.keys()
        base_path = compute_path(stream)
        regex = re.compile(r"%s~decim-(\d)+$" % base_path)
        decim_paths = list(filter(regex.match, all_paths))
        for path in [base_path, *decim_paths]:
            await self._remove_by_path(path, start, end)

    async def info(self, streams: List[Stream]) -> Dict[int, StreamInfo]:
        info_dict = await self._path_info()
        # go through each stream and compute the effective StreamInfo
        # object by looking at the raw and decimated paths
        streams_info = {}
        for s in streams:
            base_info_list = [info for (path, info) in info_dict.items() if path == compute_path(s)]
            if len(base_info_list) == 0:
                continue
            stream_info: StreamInfo = base_info_list[0]
            if stream_info.rows != 0:
                # stream has data, check for decimations
                regex = re.compile(r"%s~decim-(\d)+$" % compute_path(s))
                decim_info_list = [info for (path, info) in info_dict.items() if regex.match(path) is not None]
                for decim_info in decim_info_list:
                    if decim_info.rows == 0:
                        continue  # no data, don't try to look for start and end values
                    stream_info.start = min((stream_info.start, decim_info.start))
                    stream_info.end = max((stream_info.end, decim_info.end))
                    stream_info.bytes += decim_info.bytes
                    stream_info.total_time = max((stream_info.total_time, decim_info.total_time))
            streams_info[s.id] = stream_info
        return streams_info

    async def dbinfo(self) -> DbInfo:
        url = "{server}/dbinfo".format(server=self.server)
        async with self._get_client() as session:
            async with session.get(url) as resp:
                data = await resp.json()
                return DbInfo(**data)

    async def destroy(self, stream: Stream):
        await self.remove(stream)
        url = "{server}/stream/destroy".format(server=self.server)
        info = await self._path_info()
        all_paths = info.keys()
        base_path = compute_path(stream)
        regex = re.compile(r'%s~decim-(\d)+$' % base_path)
        decim_paths = list(filter(regex.match, all_paths))
        async with self._get_client() as session:
            for path in [base_path, *decim_paths]:
                async with session.post(url, data={"path": path}) as resp:
                    await check_for_error(resp, ignore=[ERRORS.NO_STREAM_AT_PATH])
        return web.Response(text="ok")

    async def destroy_all(self):
        raise Exception("NilmDB backend does not implement erase_all")

    async def _extract_by_path(self, path: str, start: Optional[int], end: Optional[int],
                               layout: str, callback):
        url = "{server}/stream/extract".format(server=self.server)
        params = {"path": path,
                  "binary": 1}
        decimation_factor = 1
        r = re.search(r'~decim-(\d+)$', path)
        if r is not None:
            decimation_factor = int(r[1])
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
                    reader = pipes.InputPipe(name="outbound", layout=layout, reader=resp.content)
                    while True:
                        try:
                            data = await reader.read()
                            await callback(data, layout, decimation_factor)
                            reader.consume(len(data))
                        except pipes.EmptyPipe:
                            break
                # insert the interval token to indicate a break
                await callback(pipes.interval_token(layout), layout, decimation_factor)

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
                await check_for_error(resp, ignore=[ERRORS.NO_SUCH_STREAM])
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

    async def _path_info(self) -> Dict[str, StreamInfo]:
        """ set path to None to list all streams """
        url = "{server}/stream/list".format(server=self.server)
        params = {"extended": 1}
        async with self._get_client() as session:
            async with session.get(url, params=params) as resp:
                body = await resp.text()
                if resp.status != 200:  # pragma: no cover
                    raise errors.DataError(body)
                data = json.loads(body)
                info = {}
                for item in data:
                    info[item[0]] = StreamInfo(start=item[2],
                                               end=item[3],
                                               rows=item[4],
                                               bytes=item[4] * bytes_per_row(item[1]),
                                               total_time=item[5])
                return info

    def _get_client(self):
        return aiohttp.ClientSession(connector=self.connector,
                                     loop=self.loop, connector_owner=False)

    async def close(self):
        if self.connector is not None:
            await self.connector.close()


def bytes_per_row(layout: str) -> int:
    try:
        ltype = layout.split('_')[0]
        lcount = int(layout.split('_')[1])
        if ltype.startswith('int'):
            return (int(ltype[3:]) // 8) * lcount + 8
        elif ltype.startswith('uint'):
            return (int(ltype[4:]) // 8) * lcount + 8
        elif ltype.startswith('float'):
            return (int(ltype[5:]) // 8) * lcount + 8
        else:
            raise ValueError("bad layout %s" % layout)
    except (ValueError, IndexError):
        raise ValueError("bad layout: %s" % layout)
