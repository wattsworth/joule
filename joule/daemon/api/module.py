from yarl import URL
from aiohttp import web
import aiohttp


async def get(request, socket_base):
    # remove the module and id part of the path
    path = '/'.join(request.url.parts[3:])
    module_id = request.url.parts[2]
    # connect to abstract namespace socket
    socket = b'\0'+(socket_base+module_id).encode('ascii')
    # rebuild the URL for the module
    url = URL.build(scheme="http", host="wattsworth.net", path=path)
    conn = aiohttp.UnixConnector(path=socket)
    async with aiohttp.ClientSession(connector=conn,
                                     auto_decompress=False) as session:
        # proxy the request to the module
        async with session.get(str(url)) as resp:
            raw = await resp.read()
            return web.Response(body=raw,
                                status=resp.status,
                                headers=resp.headers)

