from tests.api import mock_session
import unittest
from joule.api.node import TcpNode
from joule import errors

from joule.api.data_stream import DataStream
from joule.api.folder import Folder
from .helpers import build_stream


class TestStreamApi(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self):
        # no URL or event loop
        self.node = TcpNode('mock_node', 'http://url', 'api_key')
        self.session = mock_session.MockSession()
        self.node.session = self.session

    async def test_stream_move(self):
        # can move by ID
        await self.node.data_stream_move(1, 2)
        self.assertEqual(self.session.method, 'PUT')
        self.assertEqual(self.session.path, "/stream/move.json")
        self.assertEqual(self.session.request_data,
                         {'src_id': 1, 'dest_id': 2})
        # can move by path
        await self.node.data_stream_move('/a/path', '/b/path')
        self.assertEqual(self.session.method, 'PUT')
        self.assertEqual(self.session.path, "/stream/move.json")
        self.assertEqual(self.session.request_data,
                         {'src_path': '/a/path', 'dest_path': '/b/path'})

        # can move by Folder and DataStream
        src = DataStream()
        src.id = 1
        dest = Folder()
        dest.id = 2
        await self.node.data_stream_move(src, dest)
        self.assertEqual(self.session.path, "/stream/move.json")
        self.assertEqual(self.session.request_data,
                         {'src_id': 1, 'dest_id': 2})

    async def test_stream_move_errors(self):
        self.session.method = None
        with self.assertRaises(errors.ApiError):
            await self.node.data_stream_move(DataStream(), [])
        self.assertIsNone(self.session.method)

        with self.assertRaises(errors.ApiError):
            await self.node.data_stream_move([], Folder())
        self.assertIsNone(self.session.method)

    async def test_stream_delete(self):
        # can delete by ID
        await self.node.data_stream_delete(1)
        self.assertEqual(self.session.method, 'DELETE')
        self.assertEqual(self.session.path, "/stream.json")
        self.assertEqual(self.session.request_data, {'id': 1})
        # can delete by path
        await self.node.data_stream_delete('/a/path')
        self.assertEqual(self.session.method, 'DELETE')
        self.assertEqual(self.session.path, "/stream.json")
        self.assertEqual(self.session.request_data, {'path': '/a/path'})

        # can delete by DataStream
        src = DataStream()
        src.id = 1
        await self.node.data_stream_delete(src)
        self.assertEqual(self.session.method, 'DELETE')
        self.assertEqual(self.session.path, "/stream.json")
        self.assertEqual(self.session.request_data, {'id': 1})

    async def test_stream_delete_errors(self):
        self.session.method = None
        with self.assertRaises(errors.ApiError):
            await self.node.data_stream_delete(Folder())
        self.assertIsNone(self.session.method)

    async def test_stream_get(self):
        target = build_stream('test', 'int8[a,b]')
        target.id = 1
        self.session.response_data = target.to_json()
        stream = await self.node.data_stream_get(1)
        self.assertEqual(stream.to_json(), target.to_json())
        self.assertEqual(self.session.method, 'GET')
        self.assertEqual(self.session.path, "/stream.json")
        self.assertEqual(self.session.request_data, {'id': 1, 'no-info':''})
        # can get by path
        await self.node.data_stream_get('/a/path')
        self.assertEqual(self.session.method, 'GET')
        self.assertEqual(self.session.path, "/stream.json")
        self.assertEqual(self.session.request_data, {'path': '/a/path', 'no-info':''})

        # can get by DataStream
        src = DataStream()
        src.id = 1
        await self.node.data_stream_get(src)
        self.assertEqual(self.session.path, "/stream.json")
        self.assertEqual(self.session.request_data, {'id': 1, 'no-info':''})

    async def test_stream_get_errors(self):
        self.session.method = None
        with self.assertRaises(errors.ApiError):
            await self.node.data_stream_get(Folder())
        self.assertIsNone(self.session.method)

    async def test_local_stream_has_no_id(self):
        stream = build_stream('test', 'float64[z,y]')
        with self.assertRaises(errors.ApiError):
            stream.id
