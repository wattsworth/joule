import asyncio
import functools
from aiohttp import web
import aiohttp

from . import nilmdb
from . import module

        
async def _index(request):
    return web.Response(text="Joule API Server")


async def _version(request):
    return web.Response(text='Joule Version')


def _add_nilmdb_routes(app, nilmdb_url):

    # proxy all non-destructive /stream routes
    nilmdb_get = functools.partial(nilmdb.get, nilmdb_url=nilmdb_url)
    nilmdb_get_streaming = functools.partial(nilmdb.get_streaming,
                                             nilmdb_url=nilmdb_url)
    nilmdb_post = functools.partial(nilmdb.post,
                                    nilmdb_url=nilmdb_url)
    app.router.add_get('/dbinfo', nilmdb_get)
    app.router.add_get('/stream/list', nilmdb_get)
    app.router.add_get('/stream/intervals', nilmdb_get)
    app.router.add_get('/stream/extract', nilmdb_get_streaming)
    app.router.add_post('/stream/create', nilmdb_post)
    app.router.add_post('/stream/rename', nilmdb_post)
    app.router.add_get('/stream/get_metadata', nilmdb_get)
    app.router.add_post('/stream/set_metadata', nilmdb_post)
    app.router.add_post('/stream/update_metadata', nilmdb_post)

    
def _add_module_routes(app, modules):
    module_list = functools.partial(module.get_list,
                                    modules=modules)
    app.router.add_get('/module/list', module_list)
    module_get = functools.partial(module.get,
                                   socket_base="/tmp/wattsworth.joule.")
    app.router.add_get(r'/module/{id}', module_get)
    app.router.add_get(r'/module/{id}/{path:.*}', module_get)

                       
def build_server(loop, addr, port, nilmdb_url, modules):
    app = aiohttp.web.Application()
    _add_nilmdb_routes(app, nilmdb_url)
    _add_module_routes(app, modules)
    # proxy the dbinfo route
    app.router.add_get('/', _index)
    app.router.add_get('/version', _version)

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
