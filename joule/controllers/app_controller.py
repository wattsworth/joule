from joule.models.supervisor import Supervisor
from aiohttp import web
import logging

log = logging.getLogger("joule")


async def proxy(request: web.Request):
    supervisor: Supervisor = request.app["supervisor"]

    try:
        request_uri = request.headers["X-Original-URI"]
        request_base = request.headers["X-Original-Base"]
        uuid_str = request_uri[len(request_base)+1:].split('/')[0]
        print("Got this: %r " % uuid_str)
        if len(uuid_str) < 2:
            raise ValueError()
        uuid_type = uuid_str[0]
        uuid = int(uuid_str[1:])
    except ValueError:
        print("value error!")
        return web.Response(text="invalid id", status=400)

    # rebuild the URL for the module
    if uuid_type == 'm':  # module
        socket = supervisor.get_module_socket(uuid)
        if socket is None:
            return web.Response(text="id not found", status=404)
        proxy_path = "http://unix:%s:/" % socket

    else:  # proxy
        target_url = supervisor.get_proxy_url(uuid)
        if target_url is None:
            return web.Response(text="id not found", status=404)
        proxy_path = target_url

    print("returning proxy path: %s" % proxy_path)
    return web.Response(headers={'X-Proxy-Path': proxy_path})
