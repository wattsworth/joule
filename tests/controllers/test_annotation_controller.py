from aiohttp.test_utils import AioHTTPTestCase, unittest_run_loop
from aiohttp import web
import aiohttp

import joule.controllers
from tests.controllers.helpers import create_db
from joule.models import Stream, Annotation
from joule import utilities


class TestAnnotationController(AioHTTPTestCase):

    async def get_application(self):
        app = web.Application()
        app.add_routes(joule.controllers.routes)

        db, app["psql"] = create_db(["/top/leaf/stream1:float32[x, y, z]",
                                     "/top/middle/leaf/stream2:int8[val1, val2]"])
        self.stream1 = db.query(Stream).filter_by(name="stream1").one_or_none()
        self.stream2 = db.query(Stream).filter_by(name="stream2").one_or_none()

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

    @unittest_run_loop
    async def test_annotation_list(self):
        # 1.) retreive all annotations
        resp = await self.client.request("GET", "/annotations.json",
                                         params=[("stream_id", self.stream1.id),
                                                 ("stream_id", self.stream2.id)])
        annotations_json = await resp.json()
        self.assertEqual(len(annotations_json), 10)
        for annotation in annotations_json:
            if "stream1" in annotation["title"]:
                self.assertIsNone(annotation["end"])
            elif "stream2" in annotation["title"]:
                self.assertEqual(annotation["end"] - annotation["start"], 200)
            else:
                self.fail("invalid stream title")
        # 2.) retrieve a time bounded list
        resp = await self.client.request("GET", "/annotations.json",
                                         params={"stream_id": self.stream1.id,
                                                 "start": 500,
                                                 "end": 3500})
        annotations_json = await resp.json()
        # expect 1000, 2000, 3000 start timestamps
        self.assertEqual(len(annotations_json), 3)
        for annotation in annotations_json:
            self.assertIn("stream1", annotation["title"])
            self.assertGreater(annotation["start"], 500)
            self.assertLess(annotation["start"], 3500)

    @unittest_run_loop
    async def test_annotation_create_by_stream_id(self):
        annotation_json = {
            "title": "new_annotation",
            "content": "content",
            "start": 900,
            "end": 1000,
            "stream_id": self.stream1.id
        }
        resp = await self.client.request("POST", "/annotation.json",
                                         json=annotation_json)
        values = await resp.json()
        new_id = values["id"]
        # make sure it was added
        new_annotation = self.db.query(Annotation).get(new_id)
        self.assertEqual(new_annotation.title, "new_annotation")
        self.assertEqual(new_annotation.stream_id, self.stream1.id)
        self.assertEqual(new_annotation.start, utilities.timestamp_to_datetime(900))
        self.assertEqual(new_annotation.end, utilities.timestamp_to_datetime(1000))

    @unittest_run_loop
    async def test_annotation_create_by_stream_path(self):
        annotation_json = {
            "title": "new_annotation",
            "content": "content",
            "start": 900,
            "end": 1000,
            "stream_path": "/top/leaf/stream1"
        }
        resp = await self.client.request("POST", "/annotation.json",
                                         json=annotation_json)
        values = await resp.json()
        new_id = values["id"]
        # make sure it was added
        new_annotation = self.db.query(Annotation).get(new_id)
        self.assertEqual(new_annotation.title, "new_annotation")
        self.assertEqual(new_annotation.stream_id, self.stream1.id)
        self.assertEqual(new_annotation.start, utilities.timestamp_to_datetime(900))
        self.assertEqual(new_annotation.end, utilities.timestamp_to_datetime(1000))

    @unittest_run_loop
    async def test_annotation_edit(self):
        old_annotation = self.db.query(Annotation).filter_by(stream_id=self.stream1.id).first()
        annotation_json = {
            "title": "updated",
            "content": "this is updated too",
            "start": utilities.datetime_to_timestamp(old_annotation.start) + 100,  # should not update
            "end": 1000,  # should not update
            "id": old_annotation.id
        }
        resp = await self.client.request("PUT", "/annotation.json",
                                         json=annotation_json)
        self.assertEqual(resp.status, 200)
        new_annotation = self.db.query(Annotation).get(old_annotation.id)
        self.assertEqual(new_annotation.title, "updated")
        self.assertEqual(new_annotation.content, "this is updated too")
        self.assertEqual(new_annotation.start, old_annotation.start)
        self.assertEqual(new_annotation.end, old_annotation.end)

    @unittest_run_loop
    async def test_annotation_delete(self):
        old_annotation = self.db.query(Annotation).filter_by(stream_id=self.stream1.id).first()

        resp = await self.client.request("DELETE", "/annotation.json",
                                         params={"id": old_annotation.id})
        self.assertEqual(resp.status, 200)
        self.assertIsNone(self.db.query(Annotation).filter_by(id=old_annotation.id).one_or_none())

    @unittest_run_loop
    async def test_annotation_delete_cascade(self):
        # make sure annotation are deleted when streams are deleted
        for stream in self.db.query(Stream).all():
            self.db.delete(stream)
        self.db.commit()
        self.assertEqual(0, self.db.query(Annotation).count())

    @unittest_run_loop
    async def test_annotation_delete_all(self):
        resp = await self.client.request("DELETE", "/stream/annotations.json",
                                         params={"stream_id": self.stream1.id})
        self.assertEqual(resp.status, 200)
        self.assertEqual(0, self.db.query(Annotation).
                         filter_by(stream_id=self.stream1.id).
                         count())