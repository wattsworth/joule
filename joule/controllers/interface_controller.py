from joule.models.supervisor import Supervisor
from aiohttp import web
import aiohttp
from yarl import URL


async def proxy(request: web.Request):
    supervisor: Supervisor = request.app["supervisor"]
    try:
        module_id = int(request.url.parts[2])
    except ValueError:
        return web.Response(text="invalid module id", status=400)
    socket = supervisor.get_socket(module_id)
    if socket is None:
        return web.Response(text="module does not exist or does not have an interface",
                            status=404)
    # remove the module and id part of the path
    path = '/'.join(request.url.parts[3:])
    if path == "":
        path = "/"
    if not path.startswith('/'):
        path = '/'+path
    # rebuild the URL for the module
    url = URL.build(
        scheme=request.scheme,
        host=request.host,
        path=path,
        query=request.url.query,
        fragment=request.url.fragment)
    conn = aiohttp.UnixConnector(path=socket)
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
        return web.Response(text='Error, module interface is not available',
                            status=502)
