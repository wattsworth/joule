from aiohttp import web

from joule.models.supervisor import Supervisor
from joule import app_keys
from joule.constants import ApiErrorMessages

async def index(request):
    supervisor: Supervisor = request.app[app_keys.supervisor]
    resp = []

    for proxy in supervisor.proxies:
        proxy_info = {
            "id": proxy.uuid,
            "name": proxy.name,
            "url": str(proxy.url)
        }
        resp.append(proxy_info)
    return web.json_response(data=resp)


async def info(request):
    supervisor: Supervisor = request.app[app_keys.supervisor]
    if 'name' in request.query:
        proxy = [p for p in supervisor.proxies if p.name == request.query['name']]
    elif 'id' in request.query:
        proxy = [p for p in supervisor.proxies if p.uuid == int(request.query['id'])]
    else:
        raise web.HTTPBadRequest(reason=ApiErrorMessages.specify_id_or_path)
    if len(proxy) == 0:
        raise web.HTTPNotFound(reason="proxy does not exist")
    proxy = proxy[0]

    data = {
        "id": proxy.uuid,
        "name": proxy.name,
        "url": str(proxy.url)
    }
    return web.json_response(data)
