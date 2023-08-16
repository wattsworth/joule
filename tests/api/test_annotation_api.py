from tests.api import mock_session
import unittest

from joule.api.node import TcpNode
from joule import errors

from joule.api.data_stream import DataStream
from joule.api.annotation import Annotation


class TestAnnotationApi(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self):
        # no URL or event loop
        self.node = TcpNode('mock_node', 'http://url', 'api_key')
        self.session = mock_session.MockSession()
        self.node.session = self.session

    async def test_annotation_create(self):
        annotation = Annotation(title="note",
                                start=100,
                                content="nothing special")
        json = {
            "id": 1,
            "stream_id": 1,
            "title": "nozte",
            "start": 100,
            "end": None,
            "content": "nothing special"}
        self.session.response_data = json
        # create by stream path
        await self.node.annotation_create(annotation, '/a/path')
        self.assertEqual(self.session.request_data["stream_path"], "/a/path")
        stream = DataStream(name="test")
        stream.id = 100
        # create by DataStream object
        await self.node.annotation_create(annotation, stream)
        self.assertEqual(self.session.request_data["stream_id"], 100)
        # create by DataStream id
        await self.node.annotation_create(annotation, 100)
        self.assertEqual(self.session.request_data["stream_id"], 100)
        # errors with invalid stream type
        with self.assertRaises(errors.ApiError):
            await self.node.annotation_create(annotation, [1, 2])

    async def test_annoation_delete(self):
        annotation = Annotation(title="note",
                                start=100,
                                content="nothing special")
        annotation.id = 96
        self.session.response_data = ""
        # can delete by Annotation object
        await self.node.annotation_delete(annotation)
        self.assertEqual(self.session.request_data["id"], 96)
        # can delete by Annotation id
        await self.node.annotation_delete(annotation.id)
        self.assertEqual(self.session.request_data["id"], 96)
        # errors with invalid annotation type
        with self.assertRaises(errors.ApiError):
            await self.node.annotation_create(annotation, [1, 2])

    async def test_annotation_update(self):
        annotation = Annotation(title="note",
                                start=100,
                                content="nothing special")
        annotation.id = 1
        json = {
            "id": 1,
            "stream_id": 1,
            "title": "note",
            "start": 100,
            "end": None,
            "content": "nothing special"}
        self.session.response_data = json
        await self.node.annotation_update(annotation)
        self.assertEqual(self.session.request_data["id"], 1)

    async def test_annotation_get(self):
        json = [{
            "id": 1,
            "stream_id": 1,
            "title": "note",
            "start": 100,
            "end": None,
            "content": "nothing special"}]

        # get by stream id
        self.session.response_data = json
        await self.node.annotation_get(1)
        req_data = self.session.request_data
        self.assertEqual(req_data["stream_id"], 1)

        # get by stream object
        stream = DataStream(name="test")
        stream.id = 100
        await self.node.annotation_get(stream)
        req_data = self.session.request_data
        self.assertEqual(req_data["stream_id"], 100)

        # get by stream path
        await self.node.annotation_get("/stream/path")
        req_data = self.session.request_data
        self.assertEqual(req_data["stream_path"], "/stream/path")

        # error otherwise
        with self.assertRaises(errors.ApiError):
            await self.node.annotation_get({})









