from aiohttp import web

from joule.models.supervisor import Supervisor


async def index(request):
    supervisor: Supervisor = request.app["supervisor"]
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
    supervisor: Supervisor = request.app["supervisor"]
    if 'name' in request.query:
        proxy = [p for p in supervisor.proxies if p.name == request.query['name']]
    elif 'id' in request.query:
        proxy = [p for p in supervisor.proxies if p.uuid == int(request.query['id'])]
    else:
        return web.Response(text="specify a name or id", status=400)
    if len(proxy) == 0:
        return web.Response(text="proxy does not exist", status=404)
    proxy = proxy[0]

    data = {
        "id": proxy.uuid,
        "name": proxy.name,
        "url": str(proxy.url)
    }
    return web.json_response(data)
