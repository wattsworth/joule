import aiohttp
from joule import errors


class Session:

    def __init__(self, url: str):
        self.url = url
        self._session = None

    async def get(self, path, params=None):
        return await self._request("GET", path, params=params)

    async def post(self, path, json=None, params=None, data=None):
        return await self._request("POST", path, json=json,
                                   params=params, data=data)

    async def put(self, path, json):
        return await self._request("PUT", path, json=json)

    async def delete(self, path, params):
        return await self._request("DELETE", path, params=params)

    async def _request(self, method, path, data=None, json=None, params=None):
        if self._session is None:
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=None))
        try:
            async with self._session.request(method,
                                             self.url + path,
                                             data=data,
                                             params=params,
                                             json=json) as resp:
                if resp.status != 200:
                    raise errors.ApiError("%s [%d]" % (await resp.text(),
                                                       resp.status))
                if resp.content_type == 'application/json':
                    try:
                        result = await resp.json()
                    except ValueError:
                        raise errors.ApiError("Invalid server response (not json)")
                    return result
                else:
                    return await resp.text()

        except aiohttp.ClientError as e:
            raise errors.ApiError("Cannot contact Joule server at [%s]" %
                                  (self.url+path)) from e

    async def close(self):
        if self._session is not None:
            await self._session.close()
        self._session = None
