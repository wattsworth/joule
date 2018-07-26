from aiohttp.test_utils import AioHTTPTestCase, unittest_run_loop
from aiohttp import web
import aiohttp
import numpy as np
from sqlalchemy.orm import Session

from joule.models import folder, Stream, Folder, StreamInfo
import joule.controllers
from .helpers import create_db, MockStore
from tests import helpers

class TestDataController(AioHTTPTestCase):

    async def get_application(self):
        app = web.Application()
        app.add_routes(joule.controllers.routes)
        app["db"] = create_db(["/folder1/stream1:float32[x, y, z]",
                               "/folder2/deeper/stream2:int8[val1, val2]"])
        app["data-store"] = MockStore()
        return app

    @unittest_run_loop
    async def test_read_binary_data(self):
        db: Session = self.app["db"]
        store: MockStore = self.app["data-store"]
        nchunks = 10
        store.configure_extract(nchunks)
        resp: aiohttp.ClientResponse = await \
            self.client.get("/data", params={"path": "/folder1/stream1"})
        rx_chunks = 0
        async for _ in resp.content.iter_chunks():
            rx_chunks += 1
        self.assertEqual(nchunks, rx_chunks)

        # can retrieve stream by id as well
        stream = db.query(Stream).filter_by(name="stream1").one()
        resp: aiohttp.ClientResponse = await \
            self.client.get("/data", params={"id": stream.id})
        rx_chunks = 0
        async for _ in resp.content.iter_chunks():
            rx_chunks += 1
        self.assertEqual(nchunks, rx_chunks)

    @unittest_run_loop
    async def test_write_data(self):
        db: Session = self.app["db"]
        store: MockStore = self.app['data-store']
        stream: Stream = db.query(Stream).filter_by(name="stream1").one()
        data = helpers.create_data(stream.layout)
        resp: aiohttp.ClientResponse = await \
            self.client.post("/data", params={"path": "/folder1/stream1"},
                             data=data.tostring())
        self.assertEqual(resp.status, 200)
        self.assertTrue(store.inserted_data)

        # can write stream by id as well
        store.inserted_data = False
        data = helpers.create_data(stream.layout)
        resp: aiohttp.ClientResponse = await \
            self.client.post("/data", params={"id": stream.id},
                             data=data.tostring())
        self.assertEqual(resp.status, 200)
        self.assertTrue(store.inserted_data)

    @unittest_run_loop
    async def test_remove_data(self):
        db: Session = self.app["db"]
        store: MockStore = self.app['data-store']
        stream: Stream = db.query(Stream).filter_by(name="stream1").one()
        resp: aiohttp.ClientResponse = await \
            self.client.delete("/data", params={"path": "/folder1/stream1",
                                                "start": "100", "end": "200"})
        self.assertEqual(resp.status, 200)
        (start, end) = store.removed_data_bounds
        self.assertEqual(start, 100)
        self.assertEqual(end, 200)

        # can remove data by path as well
        resp: aiohttp.ClientResponse = await \
            self.client.delete("/data", params={"id": stream.id,
                                                "start": "800", "end": "900"})
        self.assertEqual(resp.status, 200)
        (start, end) = store.removed_data_bounds
        self.assertEqual(start, 800)
        self.assertEqual(end, 900)