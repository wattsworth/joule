from yarl import URL
import json
from aiohttp import web
import aiohttp


async def get(request, nilmdb_url):
    url = URL(nilmdb_url + request.rel_url.path)\
          .with_query(request.rel_url.query)
    async with aiohttp.ClientSession(auto_decompress=False) as session:
        async with session.get(url) as resp:
            raw = await resp.read()
            return web.Response(body=raw,
                                status=resp.status,
                                headers=resp.headers)

        
async def get_streaming(request, nilmdb_url):
    url = URL(nilmdb_url + request.rel_url.path)\
          .with_query(request.rel_url.query)
    async with aiohttp.ClientSession(auto_decompress=False) as session:
        async with session.get(url) as resp:
            # check if this is actually a streaming response
            if('Content-Length' in resp.headers):
                raw = await resp.content.read()
                return web.Response(body=raw,
                                    status=resp.status,
                                    headers=resp.headers)

            proxy_resp = web.StreamResponse(headers=resp.headers,
                                            status=resp.status)
            proxy_resp.enable_chunked_encoding()
            await proxy_resp.prepare(request)
            async for data, b in resp.content.iter_chunks():
                await proxy_resp.write(data)
            await proxy_resp.write_eof()
            return proxy_resp

        
async def post(request, nilmdb_url):
    url = URL(nilmdb_url + request.rel_url.path)
    async with aiohttp.ClientSession(auto_decompress=False) as session:
        data = await request.read()
        json_data = json.loads(data.decode('utf-8'))
        async with session.post(url, json=json_data) as resp:
            raw = await resp.read()
            return web.Response(body=raw,
                                status=resp.status,
                                headers=resp.headers)
