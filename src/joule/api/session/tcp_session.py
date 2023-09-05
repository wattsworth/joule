import ssl
import aiohttp
import asyncio
from .base_session import BaseSession
from joule import errors


# import logging
# logging.basicConfig(filename='/home/vagrant/app.log', filemode='w', format='%(name)s - %(levelname)s - %(message)s')

class TcpSession(BaseSession):

    def __init__(self, url: str, key: str, cafile: str):
        super().__init__()
        self.url = url
        self.key = key
        self.ssl_context = None
        self.cafile = cafile
        # for https nodes
        if self.url.startswith("https"):
            self.ssl_context = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
            # load cafile to verify the node
            if cafile != "":
                self.ssl_context.load_verify_locations(cafile=cafile)
            else:
                self.ssl_context.check_hostname = False
                self.ssl_context.verify_mode = ssl.CERT_NONE

    def __repr__(self):
        return "<joule.api.session.TcpSession url=\"%s\">" % self.url

    async def get_session(self):
        # make sure session is not closed, this can happen if the same
        # script has multiple asyncio.run(...) calls since each one has
        # its own event loop
        if self._session is None or self._session._loop._closed:
            self._session = aiohttp.ClientSession(
                connector=aiohttp.TCPConnector(force_close=True),
                timeout=aiohttp.ClientTimeout(total=None),
                headers={"X-API-KEY": self.key})
        return self._session

    async def _request(self, method, path, data=None, json=None, params=None, chunked=None):
        session = await self.get_session()
        try:
            # logging.warning("requesting: "+self.url+path)
            i = 0
            MAX_RETRY_COUNT = 8
            RETRY_DELAY = 2
            while i < MAX_RETRY_COUNT:
                async with session.request(method,
                                           self.url + path,
                                           data=data,
                                           params=params,
                                           json=json,
                                           chunked=chunked,
                                           ssl=self.ssl_context) as resp:
                    if resp.status != 200:
                        msg = await resp.text()
                        if resp.status > 500:
                            print("API Error: [%d], retrying %d/%d" % (resp.status, i, MAX_RETRY_COUNT))
                            i += 1
                            await asyncio.sleep(RETRY_DELAY)
                            continue  # retry
                        raise errors.ApiError("%s [%d]" % (msg, resp.status))
                    if resp.content_type != 'application/json':
                        body = await resp.text()
                        if body.lower() != "ok":
                            raise errors.ApiError("Invalid node response: %s" % body)
                        else:
                            return None
                    try:
                        # logging.warning("\trequest is done")
                        return await resp.json()
                    except ValueError:
                        raise errors.ApiError("Invalid node response (not json)")

        except ssl.CertificateError as e:
            raise errors.ApiError("the specified certificate authority did not validate this server")

        except aiohttp.ClientError as e:
            raise errors.ApiError("Cannot contact node at [%s]" % self.url) from e

        raise errors.ApiError("API Error [%d]: max retry count exceeded" % resp.status)
