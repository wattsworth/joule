from joule.models.supervisor import Supervisor
from aiohttp import web
import logging

log = logging.getLogger("joule")


async def auth(request: web.Request):
    supervisor: Supervisor = request.app["supervisor"]

    try:
        app_id = request.headers["X-App-Id"]
        if len(app_id) < 2:
            raise ValueError()
        app_type = app_id[0]
        uuid = int(app_id[1:])
    except ValueError:
        return web.Response(text="invalid id", status=400)

    # rebuild the URL for the module
    if app_type == 'm':  # module
        socket = supervisor.get_module_socket(uuid)
        if socket is None:
            return web.Response(text="id not found", status=404)
        proxy_path = "http://unix:%s:/" % socket

    else:  # proxy
        target_url = supervisor.get_proxy_url(uuid)
        if target_url is None:
            return web.Response(text="id not found", status=404)
        proxy_path = str(target_url)

    return web.Response(headers={'X-Proxy-Path': proxy_path})


async def index(request: web.Request):
    supervisor: Supervisor = request.app["supervisor"]
    apps = []
    for worker in supervisor.workers:
        if not worker.is_app:
            continue
        apps.append({'id': 'm%d' % worker.uuid,
                     'name': worker.name})
    for proxy in supervisor.proxies:
        apps.append({'id': 'p%d' % proxy.uuid,
                     'name': proxy.name})
    return web.json_response(apps)
