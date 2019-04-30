from joule.models.supervisor import Supervisor
from aiohttp import web
import aiohttp
from yarl import URL
import logging

log = logging.getLogger("joule")


async def proxy(request: web.Request):
    supervisor: Supervisor = request.app["supervisor"]

    try:
        uuid_str = request.url.parts[2]
        if len(uuid_str) < 2:
            raise ValueError()
        uuid_type = uuid_str[0]
        uuid = int(uuid_str[1:])
    except ValueError:
        return web.Response(text="invalid id", status=400)

    # remove the module and id part of the path
    path = '/'.join(request.url.parts[3:])
    root = '/' + '/'.join(request.url.parts[1:3])
    if path == "":
        path = "/"
    if not path.startswith('/'):
        path = '/' + path
    # rebuild the URL for the module
    if uuid_type == 'm':  # module
        target_url = URL.build(scheme=request.scheme,
                               host=request.host)
        socket = supervisor.get_module_socket(uuid)
        if socket is None:
            return web.Response(text="id not found", status=404)
        conn = aiohttp.UnixConnector(path=socket)
    else:  # proxy
        target_url = supervisor.get_proxy_url(uuid)
        if target_url is None:
            return web.Response(text="id not found", status=404)
        conn = aiohttp.TCPConnector()

    url = URL.build(
        scheme=target_url.scheme,
        port=target_url.port,
        host=target_url.host,
        path=path,
        query=request.url.query,
        fragment=request.url.fragment)
    try:
        async with aiohttp.ClientSession(connector=conn,
                                         auto_decompress=False) as session:
            # proxy the request to the module
            data = await request.text()
            # deny websockets, this is a TODO item
            if ('Upgrade' in request.headers and
                    request.headers['Upgrade'] == 'websocket'):
                log.warning("denying websocket for web interface [%s%d]" % (uuid_type, uuid))
                return web.Response(text="websockets are not supported", status=501)

            # add new headers for proxy information
            proxy_headers = dict(request.headers)
            proxy_headers['X-Script-Name'] = root
            proxy_headers['X-Scheme'] = url.scheme
            proxy_headers['X-Real-IP'] = request.remote
            resp = await session.request(request.method, str(url),
                                         data=data, headers=proxy_headers)
            async with resp:
                data = await resp.content.read()
                return web.Response(body=data,
                                    status=resp.status,
                                    headers=resp.headers)
    except aiohttp.ClientError:
        return web.Response(text='Error, module interface or proxy is not available',
                            status=502)
