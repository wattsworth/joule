from aiohttp import web
import os

import sys

# from https://github.com/aio-libs/aiohttp/blob/master/examples/fake_server.py


class FakeJoule:

    def __init__(self):
        self.loop = None
        self.runner = None
        self.app = web.Application()
        self.app.router.add_routes(
            [web.get('/streams.json', self.stream_list)])
        self.stream_list_response = ""
        self.stream_list_code = 200

    def start(self, port):
        sys.stdout = open(os.devnull, 'w')
        web.run_app(self.app, host='127.0.0.1', port=port)

    async def stream_list(self, request: web.Request):
        return web.Response(text=self.stream_list_response, status=self.stream_list_code)
