from aiohttp import web
import json

async def read_json(request: web.Request):
    if request.content_type != 'application/json':
        raise web.HTTPBadRequest(reason='content-type must be application/json')
    try:
        return await request.json()
    except json.DecodeError:
        raise web.HTTPBadRequest(reason='invalid json')
