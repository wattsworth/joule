from aiohttp import web
from joule.models import DataStore


async def index(request: web.Request):
    return web.Response(text="Joule server")


async def dbinfo(request: web.Request):
    data_store: DataStore = request.app["data-store"]
    data = await data_store.dbinfo()
    return web.json_response(data=data.to_json())


async def version(request: web.Request):
    return web.json_response(data={'version': "0.9"})
