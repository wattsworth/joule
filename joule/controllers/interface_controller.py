from joule.models.supervisor import Supervisor
from aiohttp import web
import aiohttp
from yarl import URL


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
    if path == "":
        path = "/"
    if not path.startswith('/'):
        path = '/'+path
    # rebuild the URL for the module
    if uuid_type == 'm':  # module
        target_url = URL.build(scheme=request.scheme,
                               host=request.host)
        socket = supervisor.get_module_socket(uuid)
        if socket is None:
            return web.Response(text="invalid id", status=400)
        conn = aiohttp.UnixConnector(path=socket)
    else:  # proxy
        target_url = supervisor.get_proxy_url(uuid)
        if target_url is None:
            return web.Response(text="invalid id", status=400)
        conn = aiohttp.TCPConnector()
    url = URL.build(
        scheme=target_url.scheme,
        host=target_url.host,
        path=path,
        query=request.url.query,
        fragment=request.url.fragment)
    try:
        async with aiohttp.ClientSession(connector=conn,
                                         auto_decompress=False) as session:
            # proxy the request to the module
            data = await request.text()
            resp = await session.request(request.method, str(url),
                                         data=data, headers=request.headers)
            async with resp:
                data = await resp.content.read()
                return web.Response(body=data,
                                    status=resp.status,
                                    headers=resp.headers)
    except aiohttp.ClientError:
        return web.Response(text='Error, module interface or proxy is not available',
                            status=502)
