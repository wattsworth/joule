import json
import aiohttp
import asyncio
import re
import numpy as np
from typing import List, Dict, Optional

from joule.models import Stream, pipes
from joule.models.data_store.data_store import DataStore, StreamInfo, Interval
from joule.models.data_store import errors


class PathNotFound(Exception):
    pass


class NilmdbStore(DataStore):

    def __init__(self, server):
        self.server = server
        self.decimation_factor = 4

    async def initialize(self, streams: List[Stream]):
        url = "{server}/stream/create".format(server=self.server)
        for stream in streams:
            data = {"path": NilmdbStore._compute_path(stream),
                    "layout": stream.layout}
            async with aiohttp.ClientSession() as session:
                async with session.post(url, data=data) as resp:
                    if resp.status != 200:
                        raise errors.DataError(await resp.text())
                return True

    async def insert(self, stream: Stream, start: int, end: int, data: np.array) -> bool:
        """insert stream data, retry on error"""
        url = "{server}/stream/insert".format(server=self.server)
        params = {"start": "%d" % start,
                  "end": "%d" % end,
                  "path": NilmdbStore._compute_path(stream),
                  "binary": '1'}
        async with aiohttp.ClientSession() as session:
            async with session.put(url, params=params,
                                   data=data.tostring()) as resp:
                if resp.status != 200:
                    error = await resp.text()
                    if resp.status == 400:
                        # nilmdb rejected the data
                        raise errors.DataError("bad data: [%s]" % error)
                    return False
                return True

    async def extract(self, stream: Stream, start: int, end: int,
                      output: asyncio.Queue = None, max_rows: int = None,
                      decimation_level=None) -> Optional(Data):
        # figure out appropriate decimation level
        if decimation_level is None:
            if max_rows is None:
                decimation_level = 1
            else:
                # find out how much data this represents
                count = await self._count_by_path(NilmdbStore._compute_path(stream),
                                                  start, end)
                desired_decimation = np.ceil(count / max_rows)
                decimation_level = 4 ** np.ceil(np.log(desired_decimation) /
                                                np.log(self.decimation_factor))
                # make sure the target decimation level exists and has data
                try:
                    path = NilmdbStore._compute_path(stream, decimation_level)
                    if self._count_by_path(path, start, end) == 0:
                        # no data in the decimated path
                        raise PathNotFound()
                except PathNotFound:
                    # no decimated data or required level does not exist
                    if output is not None:
                        # shouldn't see this normally since queue subscribers
                        # generally want raw data but anyway...
                        raise errors.InsufficientDecimation()
                    return self._intervals_by_path(NilmdbStore._compute_path(stream),
                                                   start, end)
        # retrieve data from stream
        path = NilmdbStore._compute_path(stream, decimation_level)
        await self._extract_by_path(path, start, end, stream, output)

    async def remove(self, stream, start, end):
        """ remove [start,end] in path and all decimations """
        info = await self._path_info()
        all_paths = info.keys()
        base_path = NilmdbStore._compute_path(stream)
        regex = re.compile("%s~decim-(\d)+$" % base_path)
        decim_paths = list(filter(regex.match, all_paths))
        for path in [base_path, *decim_paths]:
            await self._remove_by_path(path, start, end)

    async def info(self, stream: Stream) -> StreamInfo:
        path = NilmdbStore._compute_path(stream)
        info_dict = self._path_info(path)
        return info_dict[path]

    async def _extract_by_path(self, path: str, start: int, end: int,
                               stream: Stream, output: asyncio.Queue = None):
        url = "{server}/stream/extract".format(server=self.server)
        params = {"path": path,
                  "start": start,
                  "end": end,
                  "binary": 1}
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params) as resp:
                if output is None:
                    return await resp.text  # TODO: parse binary data
                # otherwise put data into the queue as it arrives
                reader = pipes.InputPipe(stream=stream, reader=resp.content)
                while True:
                    try:
                        data = await reader.read()
                        await output.put(data)
                        reader.consume(len(data))
                    except pipes.EmptyPipe:
                        break
        await output.put(None)

    async def _intervals_by_path(self, path, start, end) -> List[Interval]:
        url = "{server}/stream/intervals".format(server=self.server)
        params = {"path": path,
                  "start": start,
                  "end": end}
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params) as resp:
                data = await resp.text()
                return [[int(x) for x in elem] for elem in data]

    async def _remove_by_path(self, path, start, end):
        """remove data from streams"""
        url = "{server}/stream/remove".format(server=self.server)
        params = {"start": "%d" % start,
                  "end": "%d" % end,
                  "path": path}
        async with aiohttp.ClientSession() as session:
            async with session.post(url, params=params) as resp:
                if resp.status != 200:
                    raise errors.DataError(await resp.text())

    async def _count_by_path(self, path, start, end) -> int:
        url = "{server}/stream/extract".format(server=self.server)
        params = {"path": path,
                  "start": start,
                  "end": end,
                  "count": 1}
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params) as resp:
                # TODO: raise stream not found error
                return int(await resp.text())

    async def _path_info(self, path=None) -> Dict[str, StreamInfo]:
        """ set path to None to list all streams """
        url = "{server}/stream/list".format(server=self.server)
        if path is not None:
            params = {"path": path}
        else:
            params = {}
        async with aiohttp.ClientSession() as session:
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

    @staticmethod
    def _compute_path(stream: Stream, decimation_level: int = 1):
        path = "/joule/%d" % stream.id
        if decimation_level == 1:
            return path
        return path + "~decim-%d" % decimation_level
