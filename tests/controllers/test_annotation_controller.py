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
        values = await resp.json()
        stream1_annotations = values[str(self.stream1.id)]
        stream2_annotations = values[str(self.stream2.id)]
        self.assertEqual(len(stream1_annotations), 5)
        self.assertEqual(len(stream2_annotations), 5)
        for annotation in stream1_annotations:
            self.assertIn("stream1", annotation["title"])
            self.assertIsNone(annotation["end"])
        for annotation in stream2_annotations:
            self.assertIn("stream2", annotation["title"])
            self.assertEqual(annotation["end"] - annotation["start"], 200)

        # 2.) retrieve a time bounded list
        resp = await self.client.request("GET", "/annotations.json",
                                         params={"stream_id": self.stream1.id,
                                                 "start": 500,
                                                 "end": 3500})
        values = await resp.json()
        stream1_annotations = values[str(self.stream1.id)]
        # expect 1000, 2000, 3000 start timestamps
        self.assertEqual(len(stream1_annotations), 3)
        for annotation in stream1_annotations:
            self.assertIn("stream1", annotation["title"])
            self.assertGreater(annotation["start"], 500)
            self.assertLess(annotation["start"], 3500)

    @unittest_run_loop
    async def test_annotation_create(self):
        annotation_json = {
            "title": "new_annotation",
            "content": "content",
            "start": 900,
            "end": 1000,
            "stream_id": self.stream1.id
        }
        resp: aiohttp.ClientResponse = await self.client.request("POST", "/annotation.json",
                                                                 json=annotation_json)
        values = await resp.json()
        new_id = values["id"]
        # make sure it was added
        new_annotation = self.db.query(Annotation).get(new_id)
        self.assertEqual(new_annotation.title, "new_annotation")
        self.assertEqual(new_annotation.stream_id, self.stream1.id)
        self.assertEqual(new_annotation.start, utilities.timestamp_to_datetime(900))
        self.assertEqual(new_annotation.end, utilities.timestamp_to_datetime(1000))

