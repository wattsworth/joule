import aiohttp

from .base_session import BaseSession
from joule import errors


class UnixSession(BaseSession):

    def __init__(self, path: str, cafile: str):
        super().__init__()
        self.path = path
        self.url = "http://localhost"
        self.cafile = cafile

    async def get_session(self):
        if self._session is None:
            conn = aiohttp.UnixConnector(path=self.path)
            self._session = aiohttp.ClientSession(
                connector=conn,
                timeout=aiohttp.ClientTimeout(total=None))
        return self._session

    async def _request(self, method, path, data=None, json=None, params=None):
        session = await self.get_session()
        try:
            async with session.request(method,
                                       self.url + path,
                                       data=data,
                                       params=params,
                                       json=json) as resp:
                if resp.status != 200:
                    raise errors.ApiError("%s [%d]" % (await resp.text(),
                                                       resp.status))
                if resp.content_type != 'application/json':
                    body = await resp.text()
                    if body.lower() != "ok":
                        raise errors.ApiError("Invalid node response (not json)")
                    else:
                        return None
                try:
                    return await resp.json()
                except ValueError:
                    raise errors.ApiError("Invalid node response (not json)")

        except aiohttp.ClientError as e:
            raise errors.ApiError("Cannot contact node at [%s]" % self.url) from e
