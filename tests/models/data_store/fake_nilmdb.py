import socket
from typing import Dict
import pdb
import aiohttp
from aiohttp import web
from aiohttp.resolver import DefaultResolver
from aiohttp.test_utils import unused_port
import numpy as np
from tests import helpers


# from https://github.com/aio-libs/aiohttp/blob/master/examples/fake_server.py


class FakeResolver:
    _LOCAL_HOST = {0: '127.0.0.1',
                   socket.AF_INET: '127.0.0.1',
                   socket.AF_INET6: '::1'}

    def __init__(self, fakes, *, loop):
        """fakes -- dns -> port dict"""
        self._fakes = fakes
        self._resolver = DefaultResolver(loop=loop)

    async def resolve(self, host, port=0, family=socket.AF_INET):
        fake_port = self._fakes.get(host)
        if fake_port is not None:
            return [{'hostname': host,
                     'host': self._LOCAL_HOST[family], 'port': fake_port,
                     'family': family, 'proto': 0,
                     'flags': socket.AI_NUMERICHOST}]
        else:
            return await self._resolver.resolve(host, port, family)


class FakeStream:
    def __init__(self, layout, start=None, end=None, rows=0, intervals=None):
        self.layout = layout
        self.start = start
        self.end = end
        self.rows = rows
        self.intervals = intervals
        if start is not None and end is not None:
            if self.intervals is None:
                self.intervals = [[start, end]]

    @property
    def dtype(self):
        ltype = self.layout.split('_')[0]
        lcount = int(self.layout.split('_')[1])
        atype = '??'
        if ltype.startswith('int'):
            atype = '<i' + str(int(ltype[3:]) // 8)
        elif ltype.startswith('uint'):
            atype = '<u' + str(int(ltype[4:]) // 8)
        elif ltype.startswith('float'):
            atype = '<f' + str(int(ltype[5:]) // 8)
        return np.dtype([('timestamp', '<i8'), ('data', atype, lcount)])


class FakeNilmdb:

    def __init__(self, *, loop):
        self.loop = loop
        self.app = web.Application()
        self.app.router.add_routes(
            [web.post('/nilmdb/stream/create', self.stream_create),
             web.put('/nilmdb/stream/insert', self.stream_insert),
             web.get('/nilmdb/stream/extract', self.stream_extract),
             web.get('/nilmdb/stream/intervals', self.stream_intervals),
             web.post('/nilmdb/stream/remove', self.stream_remove),
             web.get('/nilmdb/stream/list', self.stream_list)])
        self.runner = None
        self.error_on_paths = {} # (msg, status) tuples to return for path
        # record of transactions
        self.posts = []
        self.gets = []
        self.extract_calls = []
        self.remove_calls = []
        # dict path=>layout from stream/create calls
        self.streams: Dict[str, FakeStream] = {}

    async def start(self):
        port = unused_port()
        self.runner = web.AppRunner(self.app)
        await self.runner.setup()
        site = web.TCPSite(self.runner, '127.0.0.1', port)
        await site.start()
        return {'test.nodes.wattsworth.net': port}

    async def stop(self):
        await self.runner.cleanup()

    def generate_error_on_path(self, path, status, msg):
        self.error_on_paths[path] = (msg, status)

    async def stream_create(self, request: web.Request):
        self.posts.append(request)
        content = await request.post()
        if content["path"] in self.streams:
            return web.json_response({
                "status": "400 Bad Request",
                "message": "stream already exists at this path",
                "traceback": ""
            }, status=400)
        self.streams[content["path"]] = FakeStream(layout=content["layout"])
        return web.json_response(None)

    async def stream_insert(self, request: web.Request):
        self.posts.append(request)
        content = request.query
        if content['path'] in self.error_on_paths:
            (msg, status) = self.error_on_paths[content['path']]
            return web.Response(status=status, text=msg)
        stream = self.streams[content["path"]]
        start = int(content["start"])
        end = int(content["end"])
        # make sure the data bounds are valid
        if stream.rows > 0:
            if ((stream.start < start < stream.end) or
                    (stream.start < end < stream.end)):
                return web.json_response({
                    "status": "400 Bad Request",
                    "message": "new data overlaps existing range XXX",
                    "traceback": ""
                }, status=400)
        # update the stored bounds
        if stream.start is None:
            stream.start = start
        elif start < stream.start:
            stream.start = start
        if stream.end is None:
            stream.end = end
        elif end > stream.end:
            stream.end = end
        # update the data rows
        raw = await request.read()
        data = np.frombuffer(raw, stream.dtype)
        stream.rows += len(data)
        return web.json_response(None)

    async def stream_extract(self, request: web.Request):
        self.extract_calls.append(request.query)
        try:
            stream = self.streams[request.query["path"]]
        except KeyError:
            return web.json_response({
                "status": "404 Not Found",
                "message": "No such stream: /joule/1",
                "traceback": ""
            }, status=404)

        if "count" in request.query:
            return web.Response(text=str(stream.rows))
        # return chunked data
        data = helpers.create_data(stream.layout, length=stream.rows)
        resp = web.StreamResponse()
        resp.enable_chunked_encoding()
        await resp.prepare(request)
        for chunk in helpers.to_chunks(data, 300):
            await resp.write(chunk.tostring())
        return resp

    async def stream_intervals(self, request: web.Request):
        try:
            stream = self.streams[request.query["path"]]
        except KeyError:
            return web.json_response({
                "status": "404 Not Found",
                "message": "No such stream: /joule/1",
                "traceback": ""
            }, status=404)
        if stream.intervals is None:
            return web.Response(status=200)

        text = "\r\n".join(["[%d, %d]" % (interval[0], interval[1]) for interval in stream.intervals])
        return web.Response(text=text)

    async def stream_remove(self, request: web.Request):
        self.remove_calls.append(request.query)
        return web.Response(text="100")

    async def stream_list(self, request: web.Request):
        return web.json_response([[path,
                                   stream.layout,
                                   stream.start,
                                   stream.end,
                                   stream.rows,
                                   stream.end - stream.start] for path, stream in self.streams.items()])
