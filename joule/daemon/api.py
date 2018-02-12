import asyncio
from aiohttp import web
import aiohttp
from yarl import URL
import json


class APIServer:

    def __init__(self, app, nilmdb_url):
        self.nilmdb_url = nilmdb_url
        self.setup_routes(app)
        
    async def index(self, request):
        return web.Response(text="Joule API Server")

    async def version(self, request):
        return web.Response(text='Joule Version')

    async def proxy_get(self, request):
        url = URL(self.nilmdb_url + request.rel_url.path)\
              .with_query(request.rel_url.query)
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                raw = await resp.read()
                return web.Response(body=raw,
                                    status=resp.status,
                                    headers=resp.headers)

    async def proxy_get_stream(self, request):
        url = URL(self.nilmdb_url + request.rel_url.path)\
              .with_query(request.rel_url.query)
        print(url)
        print("Here!")
        async with aiohttp.ClientSession() as session:
            print("session")
            async with session.get(url) as resp:
                print("resp")
                # check if this is actually a streaming response
                if('Content-Length' in resp.headers):
                    raw = await resp.read()
                    print("non-streaming")
                    print(raw)
                    return web.Response(body=raw,
                                        status=resp.status,
                                        headers=resp.headers)

                proxy_resp = web.StreamResponse(headers=resp.headers,
                                                status=resp.status)
                proxy_resp.enable_chunked_encoding()
                proxy_resp.enable_compression()
                await proxy_resp.prepare(request)
                print("beginning transmission")
                async for data, b in resp.content.iter_chunks():
                    print("sending chunk")
                    await proxy_resp.write(data)
                await proxy_resp.write_eof()
                print("all done")
                return proxy_resp

    async def proxy_post(self, request):
        url = URL(self.nilmdb_url + request.rel_url.path)
        async with aiohttp.ClientSession() as session:
            data = await request.read()
            json_data = json.loads(data.decode('utf-8'))
            async with session.post(url, json=json_data) as resp:
                raw = await resp.read()
                return web.Response(body=raw,
                                    status=resp.status,
                                    headers=resp.headers)
    
    def setup_routes(self, app):
        # proxy all non-destructive /stream routes
        app.router.add_get('/stream/list', self.proxy_get)
        app.router.add_get('/stream/intervals', self.proxy_get)
        app.router.add_get('/stream/extract', self.proxy_get_stream)
        app.router.add_post('/stream/create', self.proxy_post)
        app.router.add_post('/stream/rename', self.proxy_post)
        app.router.add_get('/stream/get_metadata', self.proxy_get)
        app.router.add_post('/stream/set_metadata', self.proxy_post)
        app.router.add_post('/stream/update_metadata', self.proxy_post)
        
        # proxy the dbinfo route
        app.router.add_get('/dbinfo', self.proxy_get)
        
        app.router.add_get('/', self.index)
        app.router.add_get('/version', self.version)


def build_server(loop, addr, port, nilmdb_url):
    app = aiohttp.web.Application()
    server = APIServer(app, nilmdb_url)
    coro = loop.create_server(app.make_handler(),
                              addr, port)
    loop.run_until_complete(coro)
    return app


if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    coro = build_server(loop,
                        '0.0.0.0',
                        port=8081,
                        nilmdb_url="http://localhost/nilmdb")
    loop.run_until_complete(coro)
    loop.run_forever()
