from aiohttp.test_utils import AioHTTPTestCase, unittest_run_loop
from aiohttp import web
import asyncio
import joule.controllers
from tests.controllers.helpers import create_db
from joule.models import DataStream, Annotation
from joule import utilities


class TestAnnotationControllerErrors(AioHTTPTestCase):

    async def get_application(self):
        app = web.Application()
        app.add_routes(joule.controllers.routes)

        # this takes a while, adjust the expected coroutine execution time
        loop = asyncio.get_running_loop()
        loop.slow_callback_duration = 2.0

        db, app["psql"] = create_db(["/top/leaf/stream1:float32[x, y, z]",
                                     "/top/middle/leaf/stream2:int8[val1, val2]"])
        self.stream1 = db.query(DataStream).filter_by(name="stream1").one_or_none()
        self.stream2 = db.query(DataStream).filter_by(name="stream2").one_or_none()

        # add 5 event annotations to stream1
        # add 5 interval annotations to stream2
        for x in range(5):
            # start: 0, 1000, 2000, 3000, 4000
            start = utilities.timestamp_to_datetime(x * 1000)
            end = utilities.timestamp_to_datetime((x * 1000) + 200)
            a1 = Annotation(title="stream1_%d" % x, start=start)
            a2 = Annotation(title="stream2_%d" % x, start=start, end=end)
            a1.stream = self.stream1
            a2.stream = self.stream2
            db.add(a1)
            db.add(a2)
        db.commit()
        app["db"] = db
        self.db = db
        return app


    async def test_annotation_list(self):
        # errors on invalid timestamps
        resp = await self.client.request("GET", "/annotations.json",
                                         params=[("stream_id", self.stream1.id),
                                                 ("stream_id", self.stream2.id),
                                                 ("start", "January 1")])
        self.assertEqual(resp.status, 400)
        self.assertIn("timestamp", await resp.text())
        # must specify at least one stream_id
        resp = await self.client.request("GET", "/annotations.json")
        self.assertEqual(resp.status, 400)
        self.assertIn("stream_id", await resp.text())
        # non-existent streams
        bad_id = self.stream1.id + self.stream2.id
        resp = await self.client.request("GET", "/annotations.json",
                                         params=[("stream_id", bad_id)])
        json = await resp.json()
        self.assertEqual(0, len(json))

        bad_path = "/bad/stream/path"
        resp = await self.client.request("GET", "/annotations.json",
                                         params=[("stream_path", bad_path)])
        self.assertIn("does not exist", await resp.text())

        self.assertEqual(resp.status, 404)


    async def test_annotation_update(self):
        # must be a json request
        resp = await self.client.request("PUT", "/annotation.json")
        self.assertEqual(resp.status, 400)
        self.assertIn("json", await resp.text())

        # must specify id
        resp = await self.client.request("PUT", "/annotation.json",
                                         json={"title": "test"})
        self.assertEqual(resp.status, 400)
        self.assertIn("id", await resp.text())
        # annotation must exist
        bad_id = 1001
        resp = await self.client.request("PUT", "/annotation.json",
                                         json={
                                             "id": bad_id,
                                             "title": "test",
                                             "content": ""})
        self.assertEqual(resp.status, 404)
        self.assertIn("does not exist", await resp.text())


    async def test_annotation_create(self):
        # must be a json request
        resp = await self.client.request("POST", "/annotation.json")
        self.assertEqual(resp.status, 400)
        self.assertIn("json", await resp.text())

        # must specify stream_id or stream_path
        resp = await self.client.request("POST", "/annotation.json",
                                         json={"title": "test"})
        self.assertEqual(resp.status, 400)
        self.assertIn("stream_id", await resp.text())
        # stream must exist
        bad_id = self.stream1.id + self.stream2.id
        resp = await self.client.request("POST", "/annotation.json",
                                         json={"stream_id": bad_id})
        self.assertEqual(resp.status, 404)
        self.assertIn("does not exist", await resp.text())
        # invalid annotation parameters
        resp = await self.client.request("POST", "/annotation.json",
                                         json={"stream_id": self.stream1.id,
                                               "title": "missing start",
                                               "end": 100})
        self.assertEqual(resp.status, 400)
        self.assertIn("invalid values", await resp.text())
        # NOTE: invalid id format is covered by middleware


    async def test_annotation_delete(self):
        # must specify an id
        resp = await self.client.request("DELETE", "/annotation.json")
        self.assertEqual(resp.status, 400)
        self.assertIn("id", await resp.text())
        # id must exist
        bad_id = 1001
        resp = await self.client.request("DELETE", "/annotation.json", params={"id": bad_id})
        self.assertEqual(resp.status, 404)
        self.assertIn("does not exist", await resp.text())


    async def test_annotation_delete_all(self):
        # must specify a stream_id
        resp = await self.client.request("DELETE", "/stream/annotations.json")
        self.assertEqual(resp.status, 400)
        self.assertIn("stream_id", await resp.text())
        # stream_id must exist
        bad_id = self.stream1.id + self.stream2.id
        resp = await self.client.request("DELETE", "/stream/annotations.json", params={"stream_id": bad_id})
        self.assertEqual(resp.status, 404)
        self.assertIn("does not exist", await resp.text())
        # start and end must be timestamps
        resp = await self.client.request("DELETE", "/stream/annotations.json",
                                         params={"stream_id": self.stream1.id,
                                                 "start": "notatimestamp"})
        self.assertEqual(resp.status, 400)
        self.assertIn("timestamp", await resp.text())
