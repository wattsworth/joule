from aiohttp.test_utils import AioHTTPTestCase, unittest_run_loop
from aiohttp import web
import aiohttp
from sqlalchemy.orm import Session

from joule.models import folder, Stream, Folder, StreamInfo
import joule.controllers
from .helpers import create_db, MockStore


class TestDataController(AioHTTPTestCase):

    async def get_application(self):
        app = web.Application()
        app.add_routes(joule.controllers.routes)
        app["db"] = create_db(["/folder1/stream1:float32[x, y, z]",
                               "/folder2/deeper/stream2:int8[val1, val2]"])
        app["data-store"] = MockStore()
        return app

    @unittest_run_loop
    async def test_read_data(self):
        db: Session = self.app["db"]
        store:MockStore = self.app["data-store"]
        nchunks=10
        store.configure_extract(nchunks)
        resp: aiohttp.ClientResponse = await \
            self.client.get("/data", params={"path": "/folder1/stream1"})
        rx_chunks = 0
        async for data in resp.content.iter_chunks():
            rx_chunks += 1
        self.assertEqual(nchunks, rx_chunks)
