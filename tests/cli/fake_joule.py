from aiohttp import web
import os
import io
from contextlib import redirect_stdout
import multiprocessing
import numpy as np
from typing import Dict, Optional, List
from aiohttp.test_utils import unused_port
import time
import signal
import json

from tests import helpers
from joule.models import Stream, StreamInfo, pipes, stream


# from https://github.com/aio-libs/aiohttp/blob/master/examples/fake_server.py


class MockDbEntry:
    def __init__(self, stream: Stream, info: StreamInfo, data: Optional[np.ndarray] = None,
                 intervals=None):
        self.stream = stream
        self.info = info
        self.data = data
        if intervals is None:
            intervals = []
        self.intervals = intervals

    def add_data(self, chunk):
        if self.data is None:
            self.data = chunk
        else:
            self.data = np.hstack((self.data, chunk))


class FakeJoule:

    def __init__(self):
        self.loop = None
        self.runner = None
        self.app = web.Application()
        self.app.router.add_routes(
            [
                web.get('/', self.info),
                web.get('/version.json', self.stub_get),
                web.get('/streams.json', self.stub_get),
                web.get('/stream.json', self.stream_info),
                web.post('/stream.json', self.create_stream),
                web.put('/stream/move.json', self.move_stream),
                web.delete('/stream.json', self.delete_stream),
                web.post('/data', self.data_write),
                web.get('/data', self.data_read),
                web.get('/data/intervals.json', self.data_intervals),
                web.delete('/data', self.data_remove),
                web.get('/modules.json', self.stub_get),
                web.get('/module.json', self.stub_get),
                web.get('/module/logs.json', self.stub_get),
                web.put('/folder/move.json', self.move_folder),
                web.delete('/folder.json', self.delete_folder)
            ])
        self.stub_stream_info = False
        self.stub_stream_move = False
        self.stub_data_remove = False
        self.stub_stream_destroy = False
        self.stub_stream_create = False
        self.stub_data_read = False
        self.stub_data_write = False
        self.stub_folder_move = False
        self.stub_folder_destroy = False
        self.response = ""
        self.http_code = 200
        self.streams: Dict[str, MockDbEntry] = {}
        self.msgs = None

    def start(self, port, msgs: multiprocessing.Queue):
        self.msgs = msgs
        f = io.StringIO()
        with redirect_stdout(f):
            web.run_app(self.app, host='127.0.0.1', port=port)

    def add_stream(self, path, my_stream: Stream, info: StreamInfo, data: Optional[np.ndarray],
                   intervals: Optional[List] = None):
        self.streams[path] = MockDbEntry(my_stream, info, data, intervals)

    async def create_stream(self, request: web.Request):
        if self.stub_stream_create:
            return web.Response(text=self.response, status=self.http_code)
        body = await request.post()
        path = body['path']
        if path == '':  # check for invalid value (eg)
            return web.Response(text='invalid request', status=400)
        new_stream = stream.from_json(json.loads(body['stream']))
        if new_stream.id is None:
            new_stream.id = 150
        else:
            new_stream.id += 100  # give the stream  a unique id

        self.streams[path + '/' + new_stream.name] = MockDbEntry(new_stream, StreamInfo(None, None, None))
        return web.json_response(data=new_stream.to_json())

    async def delete_stream(self, request: web.Request):
        if self.stub_stream_destroy:
            return web.Response(text=self.response, status=self.http_code)
        self.msgs.put(request.query['path'])
        return web.Response(text="ok")

    async def delete_folder(self, request: web.Request):
        if self.stub_folder_destroy:
            return web.Response(text=self.response, status=self.http_code)
        self.msgs.put({"path": request.query['path'],
                       "recursive": 'recursive' in request.query})
        return web.Response(text="ok")

    async def info(self, request: web.Request):
        return web.Response(text="Joule server")

    async def stub_get(self, request: web.Request):
        return web.Response(text=self.response, status=self.http_code,
                            content_type='application/json')

    async def stream_info(self, request: web.Request):
        if self.stub_stream_info or request.query['path'] == '/stub/response':
            return web.Response(text=self.response, status=self.http_code,
                                content_type='application/json')
        if request.query['path'] not in self.streams:
            return web.Response(text="stream does not exist", status=404)
        mock_entry = self.streams[request.query['path']]
        stream_json = mock_entry.stream.to_json()
        stream_json['data_info'] = mock_entry.info.to_json()
        return web.json_response(stream_json)

    async def data_remove(self, request: web.Request):
        if self.stub_data_remove:
            return web.Response(text=self.response, status=self.http_code)
        tag = '??'
        if 'path' in request.query:
            tag = request.query['path']
        elif 'id' in request.query:
            tag = request.query['id']
        self.msgs.put((tag, request.query['start'], request.query['end']))
        return web.Response(text="ok")

    async def data_read(self, request: web.Request):
        if self.stub_data_read:
            return web.Response(text=self.response, status=self.http_code)
        mock_entry = self._find_entry(request.query)
        if 'decimation-level' in request.query:
            layout = mock_entry.stream.decimated_layout
            decimation_level = request.query['decimation-level']
        else:
            layout = mock_entry.stream.layout
            decimation_level = 1
        resp = web.StreamResponse(status=200,
                                  headers={'joule-layout': layout,
                                           'joule-decimation': str(decimation_level)})
        resp.enable_chunked_encoding()
        await resp.prepare(request)
        await resp.write(mock_entry.data.tostring())
        return resp

    async def data_write(self, request: web.Request):
        if self.stub_data_write:
            return web.Response(text=self.response, status=self.http_code)

        if 'id' in request.query:
            stream_id = int(request.query['id'])
            mock_entry = [x for x in self.streams.values() if x.stream.id == stream_id][0]
        else:
            mock_entry = self.streams[request.query['path']]
        pipe = pipes.InputPipe(name="inbound", stream=mock_entry.stream, reader=request.content)
        istart = None
        iend = None
        while True:
            try:
                chunk = await pipe.read()
                if len(chunk) > 0:
                    if istart is None:
                        istart = chunk['timestamp'][0]
                    iend = chunk['timestamp'][-1]
                pipe.consume(len(chunk))
                if pipe.end_of_interval and istart is not None and iend is not None:
                    mock_entry.intervals.append([istart, iend])
                    istart = None
                    iend = None
                mock_entry.add_data(chunk)
            except pipes.EmptyPipe:
                break
        self.msgs.put(mock_entry)
        return web.Response(text="ok")

    async def data_intervals(self, request: web.Request):
        entry = self._find_entry(request.query)
        intervals = [[int(x) for x in interval] for interval in entry.intervals]

        return web.json_response(data=intervals)

    async def move_stream(self, request: web.Request):
        if self.stub_stream_move:
            return web.Response(text=self.response, status=self.http_code)
        body = await request.json()
        path = body['src_path']
        destination = body['dest_path']
        # so we can check that the message was received
        self.msgs.put((path, destination))
        return web.json_response(data={"stub": "value"})

    async def move_folder(self, request: web.Request):
        if self.stub_folder_move:
            return web.Response(text=self.response, status=self.http_code)
        body = await request.json()
        path = body['src_path']
        destination = body['dest_path']
        # so we can check that the message was received
        self.msgs.put((path, destination))
        return web.json_response(data={"stub": "value"})

    def _find_entry(self, params):
        if 'id' in params:
            stream_id = int(params['id'])
            for entry in self.streams.values():
                if entry.stream.id == stream_id:
                    return entry
            else:
                raise ValueError
        return self.streams[params['path']]


class FakeJouleTestCase(helpers.AsyncTestCase):
    def start_server(self, server):
        port = unused_port()
        self.msgs = multiprocessing.Queue()
        self.server_proc = multiprocessing.Process(target=server.start, args=(port, self.msgs))
        self.server_proc.start()
        time.sleep(0.10)
        return "http://localhost:%d" % port

    def stop_server(self):
        if self.server_proc is None:
            return
        # aiohttp doesn't always quit with SIGTERM
        os.kill(self.server_proc.pid, signal.SIGKILL)
        # join any zombies
        multiprocessing.active_children()
        self.server_proc.join()
