from joule import errors
from joule.utilities import connection_info
import aiohttp

class BaseSession:

    def __init__(self):
        self.url = ""
        self._session = None
        self.ssl_context = None
        self.cafile = ""
        self._nilmdb_checked = False
        self._nilmdb_available = False
        self._nilmdb_url = ""

    async def get_session(self):
        return self._session

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
        raise errors.ApiError("Implement in child class")

    async def close(self):
        if self._session is not None:
            await self._session.close()
        self._session = None

    async def is_nilmdb_available(self):
        # return cached result if available
        if self._nilmdb_checked:
            return self._nilmdb_available
        # this is the first time, we have to check...
        self._nilmdb_checked=True
        resp = await self.get("/db/connection.json")
        conn_info = connection_info.from_json(resp)
        if conn_info.nilmdb_url is None or conn_info.nilmdb_url == "":
            self._nilmdb_available = False
            return False # This Joule node does not use NilmDB or is out of date
        self._nilmdb_url = conn_info.nilmdb_url
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f'{self._nilmdb_url}') as response:
                    if response.status != 200:
                        raise Exception("HTTP error")
                    html = await response.text()
                    if "NilmDB" not in html:
                        raise Exception("Not a NilmDB server")
        except Exception as e:
            self._nilmdb_available = False
            return False # something went wrong with the request
        self._nilmdb_available = True
        return True # all checks passed, NilmDB is available

    def set_nilmdb_url(self, nilmdb_url):
        """Override auto check, specify nilmdb_url manually"""
        self._nilmdb_checked = True
        self._nilmdb_available = True
        self._nilmdb_url = nilmdb_url

    @property
    def nilmdb_url(self):
        if not self._nilmdb_checked:
            raise Exception("Must call is_nilmdb_available() first")
        if not self._nilmdb_available:
            raise Exception("NilmDB backend is not available")
        return self._nilmdb_url