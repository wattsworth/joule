from aiohttp import web
from joule.models import DataStore
import joule


async def index(request: web.Request):
    return web.Response(text="Joule server")


async def db_connection(request: web.Request):
    return web.json_response(data=
                             request.app["module-connection-info"].to_json())


async def dbinfo(request: web.Request):
    data_store: DataStore = request.app["data-store"]
    data = await data_store.dbinfo()
    return web.json_response(data=data.to_json())


async def version_json(request: web.Request):
    return web.json_response(data={'version': joule.__version__,
                                   'name': request.app['name']})


async def version(request: web.Request):
    return web.Response(text=joule.__version__)
