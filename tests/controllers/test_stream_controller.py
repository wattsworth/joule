from aiohttp.test_utils import AioHTTPTestCase, unittest_run_loop
from aiohttp import web
import aiohttp
from sqlalchemy.orm import Session

from joule.models import folder, DataStream, Folder, Element, StreamInfo
import joule.controllers
from tests.controllers.helpers import create_db, MockStore


class TestStreamController(AioHTTPTestCase):

    async def tearDownAsync(self):
        self.app["db"].close()
        self.app["psql"].stop()

    async def get_application(self):
        app = web.Application()
        app.add_routes(joule.controllers.routes)
        app["db"], app["psql"] = create_db(["/folder1/stream1:float32[x, y, z]",
                                            "/folder2/deeper/stream2:int8[val1, val2]"])
        app["data-store"] = MockStore()
        return app

    @unittest_run_loop
    async def test_stream_info(self):
        db: Session = self.app["db"]
        my_stream: DataStream = db.query(DataStream).filter_by(name="stream1").one()
        store: MockStore = self.app["data-store"]
        mock_info = StreamInfo(start=0, end=100, rows=200)
        store.set_info(my_stream, mock_info)
        # can query by id
        resp = await self.client.request("GET", "/stream.json?id=%d" % my_stream.id)
        actual = await resp.json()
        expected = my_stream.to_json({my_stream.id: mock_info})
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
            "src_path": "/folder1/stream1",
            "dest_path": "/new/folder3"
        }
        resp = await self.client.put("/stream/move.json", json=payload)
        self.assertEqual(resp.status, 200)
        folder3 = db.query(Folder).filter_by(name="folder3").one()
        folder1 = db.query(Folder).filter_by(name="folder1").one()
        # check the destination
        self.assertEqual(folder3.data_streams[0].name, "stream1")
        self.assertEqual(folder3.parent.name, "new")
        # check the source
        self.assertEqual(len(folder1.data_streams), 0)
        # move stream1 back to folder1
        payload = {
            "src_path": "/new/folder3/stream1",
            "dest_id": folder1.id
        }
        resp = await self.client.put("/stream/move.json", json=payload)
        self.assertEqual(resp.status, 200)
        # check the destination
        self.assertEqual(folder1.data_streams[0].name, "stream1")
        # check the source
        self.assertEqual(len(folder3.data_streams), 0)

    @unittest_run_loop
    async def test_stream_create(self):
        db: Session = self.app["db"]
        new_stream = DataStream(name="test", datatype=DataStream.DATATYPE.FLOAT32)
        new_stream.elements = [Element(name="e%d" % j, index=j,
                                       display_type=Element.DISPLAYTYPE.CONTINUOUS) for j in range(3)]
        payload = {
            "dest_path": "/deep/new folder",
            "stream": new_stream.to_json()
        }
        resp = await self.client.post("/stream.json", json=payload)

        self.assertEqual(resp.status, 200)
        # check the stream was created correctly
        created_stream: DataStream = db.query(DataStream).filter_by(name="test").one()
        self.assertEqual(len(created_stream.elements), len(new_stream.elements))
        self.assertEqual(created_stream.folder.name, "new folder")

        # can create by dest_id as well
        folder1: Folder = db.query(Folder).filter_by(name="folder1").one()
        new_stream.name = "test2"
        payload = {
            "dest_id": folder1.id,
            "stream": new_stream.to_json()
        }
        resp = await self.client.post("/stream.json", json=payload)

        self.assertEqual(resp.status, 200)
        # check the stream was created correctly
        created_stream: DataStream = db.query(DataStream).filter_by(name="test2").one()
        self.assertEqual(len(created_stream.elements), len(new_stream.elements))
        self.assertEqual(created_stream.folder.name, "folder1")

    @unittest_run_loop
    async def test_stream_delete_by_path(self):
        db: Session = self.app["db"]
        my_stream: DataStream = db.query(DataStream).filter_by(name="stream1").one()
        store: MockStore = self.app["data-store"]
        payload = {'path': "/folder1/stream1"}
        resp = await self.client.delete("/stream.json", params=payload)
        self.assertEqual(resp.status, 200)
        # make sure it was removed from the data store
        self.assertEqual(store.destroyed_stream_id, my_stream.id)
        # and the metadata
        self.assertEqual(0, db.query(DataStream).filter_by(name="stream1").count())

    @unittest_run_loop
    async def test_stream_delete_by_id(self):
        db: Session = self.app["db"]
        my_stream: DataStream = db.query(DataStream).filter_by(name="stream1").one()
        store: MockStore = self.app["data-store"]
        payload = {'id': my_stream.id}
        resp = await self.client.delete("/stream.json", params=payload)
        self.assertEqual(resp.status, 200)
        # make sure it was removed from the data store
        self.assertEqual(store.destroyed_stream_id, my_stream.id)
        # and the metadata
        self.assertEqual(0, db.query(DataStream).filter_by(name="stream1").count())

    @unittest_run_loop
    async def test_stream_update(self):
        db: Session = self.app["db"]
        my_stream: DataStream = db.query(DataStream).filter_by(name="stream1").one()
        # change the stream name
        payload = {
            "id": my_stream.id,
            "stream": {"name": "new name"}
        }
        resp = await self.client.put("/stream.json", json=payload)
        self.assertEqual(resp.status, 200)
        my_stream: DataStream = db.query(DataStream).get(my_stream.id)
        self.assertEqual("new name", my_stream.name)
