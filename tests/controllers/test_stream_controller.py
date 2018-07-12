from aiohttp.test_utils import AioHTTPTestCase, unittest_run_loop
from aiohttp import web
import aiohttp
from sqlalchemy.orm import Session

from joule.models import folder, Stream, Folder, StreamInfo
import joule.controllers
from .helpers import create_db, MockStore


class TestStreamController(AioHTTPTestCase):

    async def get_application(self):
        app = web.Application()
        app.add_routes(joule.controllers.routes)
        app["db"] = create_db(["/folder1/stream1:float32[x, y, z]",
                               "/folder2/deeper/stream2:int8[val1, val2]"])
        app["data-store"] = MockStore()
        return app

    @unittest_run_loop
    async def test_stream_list(self):
        db: Session = self.app["db"]
        resp: aiohttp.ClientResponse = await self.client.request("GET", "/streams.json")
        actual = await resp.json()
        # basic check to see if JSON response matches database structure
        expected = folder.root(db).to_json()
        self.assertEqual(actual, expected)

    @unittest_run_loop
    async def test_stream_info(self):
        db: Session = self.app["db"]
        my_stream: Stream = db.query(Stream).filter_by(name="stream1").one()
        store: MockStore = self.app["data-store"]
        mock_info = StreamInfo(start=0, end=100, rows=200)
        store.set_info(my_stream, mock_info)
        # can query by id
        resp = await self.client.request("GET", "/stream.json?id=%d" % my_stream.id)
        actual = await resp.json()
        expected = {"stream": my_stream.to_json(), "data_info": mock_info.to_json()}
        self.assertEqual(actual, expected)
        # can query by path
        payload = {'path': "/folder1/stream1"}
        resp = await self.client.request("GET", "/stream.json", params=payload)
        actual = await resp.json()
        self.assertEqual(actual, expected)

    @unittest_run_loop
    async def test_stream_move(self):
        db: Session = self.app["db"]
        # move stream1 into folder3
        payload = {
            "path": "/folder1/stream1",
            "destination": "/new/folder3"
        }
        resp = await self.client.put("/stream/move.json", data=payload)
        self.assertEqual(resp.status, 200)
        folder3 = db.query(Folder).filter_by(name="folder3").one()
        folder1 = db.query(Folder).filter_by(name="folder1").one()
        # check the destination
        self.assertEqual(folder3.streams[0].name, "stream1")
        self.assertEqual(folder3.parent.name, "new")
        # check the source
        self.assertEqual(len(folder1.streams), 0)
