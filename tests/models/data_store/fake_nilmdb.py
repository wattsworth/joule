from typing import Dict
from aiohttp import web
from aiohttp.test_utils import unused_port
import numpy as np
import multiprocessing
from tests import helpers


class FakeStream:
    def __init__(self, layout, start=None, end=None, rows=0, intervals=None):
        self.layout = layout
        self.start = start
        self.end = end
        self.rows = rows
        self.intervals = intervals
        self.metadata = {}
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

    def __init__(self):
        self.app = web.Application()
        self.app.router.add_routes(
            [web.get('/', self.info),
             web.get('/dbinfo', self.dbinfo),
             web.get('/stream/get_metadata', self.stream_get_metadata),
             web.post('/stream/set_metadata', self.stream_set_metadata),
             web.post('/stream/create', self.stream_create),
             web.put('/stream/insert', self.stream_insert),
             web.get('/stream/extract', self.stream_extract),
             web.get('/stream/intervals', self.stream_intervals),
             web.post('/stream/remove', self.stream_remove),
             web.get('/stream/list', self.stream_list),
             web.post('/stream/destroy', self.stream_destroy)])
        self.runner = None
        self.error_on_paths = {}  # (msg, status) tuples to return for path
        self.stub_stream_create = False
        self.stub_stream_intervals = False
        self.http_code = 200
        self.response = ''
        # record of transactions
        self.posts = []
        self.gets = []
        self.extract_calls = []
        self.remove_calls = []
        self.destroy_calls = []
        self.stream_list_response = None
        # dict path=>layout from stream/create calls
        self.streams: Dict[str, FakeStream] = {}
        # optional queue of messages
        self.msgs: multiprocessing.Queue = None

    async def start(self, port=None, msgs: multiprocessing.Queue=None):
        if port is None:
            port = unused_port()
        self.runner = web.AppRunner(self.app)
        await self.runner.setup()
        site = web.TCPSite(self.runner, '127.0.0.1', port)
        await site.start()
        self.msgs = msgs
        return "http://localhost:%d" % port

    async def stop(self):
        await self.runner.cleanup()

    def generate_error_on_path(self, path, status, msg):
        self.error_on_paths[path] = (msg, status)

    async def info(self, request: web.Request):
        return web.Response(text="This is NilmDB version 1.11.0, running on host unittest")

    async def dbinfo(self, request: web.Request):
        return web.json_response(data={"path": "/opt/data",
                                       "other": 36002418688,
                                       "reserved": 11639611392,
                                       "free": 178200829952,
                                       "size": 2832261120})

    async def stream_create(self, request: web.Request):
        self.posts.append(request)
        if self.stub_stream_create:
            return web.Response(status=self.http_code, text=self.response)
        content = await request.post()

        if self.msgs is not None:
            self.msgs.put({'action': 'stream_create',
                           'params': dict(content)})

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
        if self.msgs is not None:
            self.msgs.put({'action': 'stream_insert',
                           'params': dict(content), 'data': data})
        return web.json_response(None)

    async def stream_extract(self, request: web.Request):
        self.extract_calls.append(request.query)
        try:
            stream = self.streams[request.query["path"]]
        except KeyError:
            return web.json_response({
                "status": "404 Not Found",
                "message": "No such stream: %s" % request.query["path"],
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
            await resp.write(chunk.tobytes())
        return resp

    async def stream_intervals(self, request: web.Request):
        if self.stub_stream_intervals:
            return web.Response(status=self.http_code, text=self.response)
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

    async def stream_destroy(self, request: web.Request):
        content = await request.post()
        self.destroy_calls.append(content)
        return web.json_response(data=None)

    async def stream_list(self, request: web.Request):
        if self.stream_list_response is not None:
            return web.Response(text=self.stream_list_response)
        return web.json_response([[path,
                                   stream.layout,
                                   stream.start,
                                   stream.end,
                                   stream.rows,
                                   stream.end - stream.start] for path, stream in self.streams.items()])

    async def stream_get_metadata(self, request: web.Request):
        try:
            stream = self.streams[request.query["path"]]
            return web.json_response(stream.metadata)
        except KeyError:
            return web.Response(status=404)

    async def stream_set_metadata(self, request: web.Request):
        content = await request.post()
        if self.msgs is not None:
            self.msgs.put({'action': 'set_metadata',
                           'params': dict(content)})
        try:
            stream = self.streams[content["path"]]
            stream.metadata = dict(content)
        except KeyError:
            return web.Response(status=404)
        return web.Response(text="ok")
