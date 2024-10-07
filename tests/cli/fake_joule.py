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
import asyncio
import json
import psutil
import tempfile


from tests import helpers
from joule.models import DataStream, StreamInfo, pipes, data_stream, master
from joule.api import annotation
from joule.constants import EndPoints, ConfigFiles
from joule.errors import EmptyPipeError
# from https://github.com/aio-libs/aiohttp/blob/master/examples/fake_server.py


class MockDbEntry:
    def __init__(self, stream: DataStream, info: StreamInfo, data: Optional[np.ndarray] = None,
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
        self.runner = None
        self.app = web.Application(middlewares=[self._authorize])

        self.app.router.add_routes(
            [
                web.get(EndPoints.root, self.info),
                # GET db_connection
                web.get(EndPoints.db_info, self.dbinfo),
                # GET version
                web.get(EndPoints.version_json, self.stub_get),
                # --- event stream routes ---
                web.get(EndPoints.event, self.stub_get),
                web.put(EndPoints.event_move, self.move_stream),
                web.put(EndPoints.event, self.update_stream),
                #web.post(EndPoints.event, None),
                web.delete(EndPoints.event, self.delete_stream),
                # --- event stream data routes ---
                #web.get(EndPoints.event_data, None),
                #web.get(EndPoints.event_data_count, None),
                #web.post(EndPoints.event_data, None),
                #web.delete(EndPoints.event_data, None),
                # --- stream routes ---

                web.get(EndPoints.stream, self.stream_info),
                web.put(EndPoints.stream_move, self.move_stream),
                web.put(EndPoints.stream, self.update_stream),
                web.post(EndPoints.stream, self.create_stream),
                web.delete(EndPoints.stream, self.delete_stream),
                # --- folder routes ---
                web.get(EndPoints.folders, self.stub_get),
                web.get(EndPoints.folder, self.folder_info),
                web.put(EndPoints.folder_move, self.move_folder),
                web.put(EndPoints.folder, self.update_folder),
                web.delete(EndPoints.folder, self.delete_folder),
                # --- data routes ---
                web.get(EndPoints.data, self.data_read),
                # GET data.json
                web.get(EndPoints.data_intervals, self.data_intervals),
                web.post(EndPoints.data_decimate, self.data_decimate),
                # DELETE data_decimate
                web.post(EndPoints.data_consolidate, self.data_consolidate),
                web.post(EndPoints.data, self.data_write),
                web.delete(EndPoints.data, self.data_delete),
                # --- module routes ---
                web.get(EndPoints.modules, self.stub_get),
                web.get(EndPoints.module, self.stub_get),
                web.get(EndPoints.module_logs, self.stub_get),
                # --- app routes ---
                # GET app_auth
                # GET app_json
                # --- proxy routes ---
                web.get(EndPoints.proxies, self.stub_get),
                web.get(EndPoints.proxy, self.stub_get),
                # -- master routes --
                web.get(EndPoints.masters, self.stub_get),
                web.post(EndPoints.master, self.create_master),
                web.delete(EndPoints.master, self.delete_master),
                # --- follower routes ---
                web.get(EndPoints.followers, self.stub_get),
                # POST follower
                web.delete(EndPoints.follower, self.stub_get),
                # -- annotation routes --
                web.get(EndPoints.annotations_info, self.get_annotation_info),
                web.get(EndPoints.annotations, self.get_annotations),
                web.put(EndPoints.annotation, self.update_annotation),
                web.post(EndPoints.annotation, self.create_annotation),
                web.delete(EndPoints.annotation, self.delete_annotation),
                web.delete(EndPoints.stream_annotations, self.delete_all_annotations),

                
                # --- event stream data routes ---

            ])
        self.stub_stream_info = False
        self.stub_stream_move = False
        self.stub_data_delete = False
        self.stub_stream_destroy = False
        self.stub_stream_create = False
        self.stub_data_read = False
        self.stub_data_write = False
        self.stub_folder_move = False
        self.stub_folder_destroy = False
        self.stub_folder_info = False
        self.stub_folder_update = False
        self.stub_data_intervals = False
        self.stub_data_consolidate = False
        self.stub_data_decimate = False
        self.stub_master = False
        self.stub_stream_update = False
        self.stub_annotation = False
        self.first_lumen_user = True
        self.response = ""
        # need this because node info cmd makes two requests
        self.dbinfo_response = "--fill-in--"
        self.num_consolidated = 5
        self.http_code = 200
        self.streams: Dict[str, MockDbEntry] = {}
        self.msgs = None
        self.key = "invalid"

    def start(self, port, msgs: multiprocessing.Queue, inbound_msgs, key):
        self.msgs = msgs
        self.key = key
        #f = io.StringIO()
        #with redirect_stdout(f):
        #web.run_app(self.app, host='127.0.0.1', port=port,
        #                handle_signals=True)
        #''
        #asyncio.run(self._run_server(port, inbound_msgs))
        asyncio.run(self._run_server(port, inbound_msgs))
        msgs.close()
        inbound_msgs.close()
        msgs.join_thread()
        inbound_msgs.join_thread()

    @web.middleware
    async def _authorize(self, request, handler):
        if 'X-API-KEY' not in request.headers:
            raise web.HTTPForbidden()
        key = request.headers['X-API-KEY']
        if key != self.key:
            raise web.HTTPForbidden()
        return await handler(request)

    async def _run_server(self, port, msgs):
        runner = web.AppRunner(self.app)
        await runner.setup()
        site = web.TCPSite(runner, 'localhost', port)
        await site.start()

        while 1:
            await asyncio.sleep(0.1)
            if not msgs.empty():
                msgs.get()
                break
        await runner.cleanup()

    def add_stream(self, path, my_stream: DataStream, info: StreamInfo, data: Optional[np.ndarray],
                   intervals: Optional[List] = None):
        self.streams[path] = MockDbEntry(my_stream, info, data, intervals)

    async def create_stream(self, request: web.Request):
        if self.stub_stream_create:
            return web.Response(text=self.response, status=self.http_code)
        body = await request.json()
        path = body['dest_path']
        if path == '':  # check for invalid value (eg)
            return web.Response(text='invalid request', status=400)
        new_stream = data_stream.from_json(body['stream'])
        if new_stream.id is None:
            new_stream.id = 150
        else:
            new_stream.id += 100  # give the stream  a unique id
        self.streams[path + '/' + new_stream.name] = MockDbEntry(new_stream, StreamInfo(None, None, None))
        return web.json_response(data=new_stream.to_json())

    async def update_stream(self, request: web.Request):
        if self.stub_stream_update:
            return web.Response(text=self.response, status=self.http_code)
        body = await request.json()
        # so we can check that the message was received
        self.msgs.put(dict(body['stream']))
        return web.json_response(data={"stub": "value"})

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

    async def dbinfo(self, request: web.Request):
        return web.Response(text=self.dbinfo_response, status=self.http_code,
                            content_type='application/json')

    async def stub_get(self, request: web.Request):
        return web.Response(text=self.response, status=self.http_code,
                            content_type='application/json')

    async def stream_info(self, request: web.Request):
        if self.stub_stream_info or \
                ('path' in request.query and request.query['path'] == '/stub/response'):
            return web.Response(text=self.response, status=self.http_code,
                                content_type='application/json')
        try:
            mock_entry = self._find_entry(request.query)
        except ValueError:
            return web.Response(text="stream does not exist", status=404)
        stream_json = mock_entry.stream.to_json()
        stream_json['data_info'] = mock_entry.info.to_json()
        return web.json_response(stream_json)

    async def folder_info(self, request: web.Request):
        if self.stub_folder_info:
            return web.Response(text=self.response, status=self.http_code,
                                content_type='application/json')
        # this endpoint must be stubbed
        return web.Response(text="NOT IMPLEMENTED", status=500)

    async def data_delete(self, request: web.Request):
        if self.stub_data_delete:
            return web.Response(text=self.response, status=self.http_code)
        tag = '??'
        if 'path' in request.query:
            tag = request.query['path']
        elif 'id' in request.query:
            tag = request.query['id']
        start = None
        if 'start'in request.query:
            start = int(request.query['start'])
        end = None
        if 'end' in request.query:
            end = int(request.query['end'])
        self.msgs.put((tag, start, end))
        return web.Response(text="ok")

    async def data_read(self, request: web.Request):
        if self.stub_data_read:
            return web.Response(text=self.response, status=self.http_code)
        mock_entry = self._find_entry(request.query)
        if 'decimation-level' in request.query:
            layout = mock_entry.stream.decimated_layout
            decimation_level = request.query['decimation-level']
        elif 'max-rows' in request.query:
            layout = mock_entry.stream.decimated_layout
            decimation_level = 16 # just made up
        else:
            layout = mock_entry.stream.layout
            decimation_level = 1
        resp = web.StreamResponse(status=200,
                                  headers={'joule-layout': layout,
                                           'joule-decimation': str(decimation_level)})
        resp.enable_chunked_encoding()
        await resp.prepare(request)
        await resp.write(mock_entry.data.tobytes())
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
            except EmptyPipeError:
                break
        self.msgs.put(mock_entry)
        return web.Response(text="ok")

    async def data_intervals(self, request: web.Request):
        if self.stub_data_intervals:
            return web.Response(text=self.response, status=self.http_code)
        entry = self._find_entry(request.query)
        intervals = [[int(x) for x in interval] for interval in entry.intervals]

        return web.json_response(data=intervals)

    async def data_consolidate(self, request: web.Request):
        if self.stub_data_consolidate:
            return web.Response(text=self.response, status=self.http_code)
        path = request.query['path']
        start = None
        if 'start'in request.query:
            start = int(request.query['start'])
        end = None
        if 'end' in request.query:
            end = int(request.query['end'])
        max_gap = int(request.query['max_gap'])
        self.msgs.put((path, start, end, max_gap))
        return web.json_response(data={"num_consolidated": self.num_consolidated})
    
    async def data_decimate(self, request: web.Request):
        if self.stub_data_decimate:
            return web.Response(text=self.response, status=self.http_code)
        path = request.query['path']
        self.msgs.put(('decimate',path))
        return web.Response(text="ok")
    
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

    async def update_folder(self, request: web.Request):
        if self.stub_folder_update:
            return web.Response(text=self.response, status=self.http_code)
        body = await request.json()
        # so we can check that the message was received
        self.msgs.put(dict(body['folder']))
        return web.json_response(data={"stub": "value"})

    async def create_master(self, request: web.Request):
        if self.stub_master:
            return web.Response(text=self.response, status=self.http_code)
        body = await request.json()
        if body["master_type"] == "user":
            self.msgs.put(body)
            return web.json_response({"key": "fakekey", "name": body["identifier"]})
        if body["master_type"] == "joule":
            self.msgs.put(body)
            return web.json_response({"name": body["identifier"]})
        if body["master_type"] == "lumen":
            if len(body["lumen_params"]) == 0:
                if self.first_lumen_user:
                    self.first_lumen_user = False
                    return web.Response(text="first_name")
                else:
                    return web.Response(text="auth_key", status=400)
            lumen_params = body["lumen_params"]
            self.msgs.put(lumen_params)
            return web.json_response({"name": body["identifier"]})

    async def delete_master(self, request: web.Request):
        if self.stub_master:
            return web.Response(text=self.response, status=self.http_code)
        self.msgs.put(request.query['name'])
        return web.Response(text="ok")

    async def get_annotation_info(self, request: web.Request):
        # stub annotation info
        info = {
            'start': 0,
            'end': 10e6,
            'count': 10
        }
        return web.Response(text=json.dumps(info), status=self.http_code,
                            content_type='application/json')

    async def get_annotations(self, request: web.Request):
        self.msgs.put(dict(request.query))

        resp = self.response
        if resp == "":
            resp = "[]" # so a call to get_annotations returns an empty list
        return web.Response(text=resp, status=self.http_code,
                            content_type='application/json')

    async def update_annotation(self, request: web.Request):
        if self.stub_annotation:
            return web.Response(text=self.response, status=self.http_code)
        body = await request.json()
        title = body['title']
        content = body['content']
        # so we can check that the message was received
        self.msgs.put((title, content))
        return web.json_response(data={"stub": "value"})

    async def create_annotation(self, request: web.Request):
        if self.stub_annotation:
            return web.Response(text=self.response, status=self.http_code)
        body = await request.json()
        body["id"] = 1
        # so we can check that the message was received
        self.msgs.put((annotation.from_json(body)))
        return web.json_response(data=body)

    async def delete_annotation(self, request: web.Request):
        if self.stub_annotation:
            return web.Response(text=self.response, status=self.http_code)

        self.msgs.put(request.query['id'])
        return web.json_response(text="ok")

    async def delete_all_annotations(self, request: web.Request):
        if self.stub_annotation:
            return web.Response(text=self.response, status=self.http_code)

        self.msgs.put(dict(request.query))
        return web.Response(text="ok")


    def _find_entry(self, params):
        if 'id' in params:
            stream_id = int(params['id'])
            for entry in self.streams.values():
                if entry.stream.id == stream_id:
                    return entry
            else:
                raise ValueError
        else:
            path = params['path']
            if path not in self.streams:
                raise ValueError
            return self.streams[params['path']]


class FakeJouleTestCase(helpers.AsyncTestCase):
    def start_server(self, server):
        key = master.make_key()
        self.proc = psutil.Process()
        port = unused_port()
        self.msgs = multiprocessing.Queue()
        self.outbound_msgs = multiprocessing.Queue()
        self.server_proc = multiprocessing.Process(target=server.start,
                                                   args=(port,
                                                         self.msgs,
                                                         self.outbound_msgs,
                                                         key))
        self.server_proc.start()
        ready = False
        time.sleep(0.01)
        self.conf_dir = tempfile.TemporaryDirectory()
        while not ready:
            for conn in psutil.net_connections():
                if conn.laddr.port == port:
                    ready = True
                    break
            else:
                time.sleep(0.1)
        # create a .joule config directory with key info
        with open(os.path.join(self.conf_dir.name, ConfigFiles.nodes), 'w') as f:
            f.write(json.dumps([{"name": "fake_joule",
                                 "key": key,
                                 "url": "http://127.0.0.1:%d" % port}]))
        with open(os.path.join(self.conf_dir.name, ConfigFiles.default_node), 'w') as f:
            f.write("fake_joule")
        os.environ["JOULE_USER_CONFIG_DIR"] = self.conf_dir.name

    def stop_server(self):
        if self.server_proc is None:
            return

        self.msgs.close()
        self.msgs.join_thread()

        self.outbound_msgs.put("stop")
        self.outbound_msgs.close()
        while self.server_proc.is_alive():
            time.sleep(0.01)
        self.outbound_msgs.close()
        self.outbound_msgs.join_thread()
        # join any zombies
        self.server_proc.join()
        # force delete to close underlying pipes
        del self.outbound_msgs
        del self.msgs
        del self.server_proc
        self.conf_dir.cleanup()
        del os.environ["JOULE_USER_CONFIG_DIR"]

    def assertCliSuccess(self, cli_result):
        if cli_result.exit_code != 0:
            print("#### Error CLI Output #####: ")
            print(cli_result.output)
        self.assertEqual(cli_result.exit_code, 0)

### Helper functions
def print_result_on_error(result):
    if result.exit_code != 0:
        print("output: ", result.output)
        print("exception: ", result.exception)