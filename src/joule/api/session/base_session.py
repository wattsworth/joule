from joule import errors
from joule.utilities import connection_info
import aiohttp

class BaseSession:

    def __init__(self):
        self.url = ""
        self._session = None
        self.ssl_context = None
        self.cafile = ""

    async def get_session(self):
        raise errors.ApiError("Implement in child class") # pragma: no cover

    async def get(self, path, params=None):
        return await self._request("GET", path, params=params)

    async def post(self, path, json=None, params=None, data=None, chunked=None):
        return await self._request("POST", path, json=json,
                                   params=params, data=data, chunked=chunked)

    async def put(self, path, json):
        return await self._request("PUT", path, json=json)

    async def delete(self, path, params):
        return await self._request("DELETE", path, params=params)

    async def _request(self, method, path, data=None, json=None, params=None, chunked=None):
        raise errors.ApiError("Implement in child class") # pragma: no cover

    async def close(self):
        if self._session is not None:
            await self._session.close()
        self._session = None
