from joule.models.supervisor import Supervisor
from aiohttp import web
import logging
from joule import app_keys
from joule.constants import ApiErrorMessages

log = logging.getLogger("joule")


async def auth(request: web.Request):
    supervisor: Supervisor = request.app[app_keys.supervisor]

    try:
        app_id = request.headers["X-App-Id"]
        if len(app_id) < 2:
            raise ValueError()
        app_type = app_id[0]
        uuid = int(app_id[1:])
    except ValueError:
        raise web.HTTPBadRequest(reason="invalid id")
    
    # rebuild the URL for the module
    if app_type == 'm':  # module
        socket = supervisor.get_module_socket(uuid)
        if socket is None:
            raise web.HTTPNotFound(reason=ApiErrorMessages.id_not_found)
        proxy_path = "http://unix:%s:/" % socket

    elif app_type == 'p':  # proxy
        target_url = supervisor.get_proxy_url(uuid)
        if target_url is None:
            raise web.HTTPNotFound(reason=ApiErrorMessages.id_not_found)
        proxy_path = str(target_url)

    else:
        raise web.HTTPBadRequest(reason="invalid id")
    
    return web.Response(headers={'X-Proxy-Path': proxy_path})


async def index(request: web.Request):
    supervisor: Supervisor = request.app[app_keys.supervisor]
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
