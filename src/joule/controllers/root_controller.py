from aiohttp import web
from joule.models import DataStore
import joule
import pkg_resources
from joule import app_keys
async def index(request: web.Request):
    return web.Response(text="Joule server")


async def db_connection(request: web.Request):
    return web.json_response(data=
                             request.app[app_keys.module_connection_info].to_json())


async def dbinfo(request: web.Request):
    data_store: DataStore = request.app[app_keys.data_store]
    data = await data_store.dbinfo()
    return web.json_response(data=data.to_json())


async def version_json(request: web.Request):
    return web.json_response(data={'version': pkg_resources.get_distribution('joule').version,
                                   'name': request.app[app_keys.name],
                                   'uuid': str(request.app[app_keys.uuid])})


async def version(request: web.Request):
    return web.Response(text=pkg_resources.get_distribution('joule').version)
