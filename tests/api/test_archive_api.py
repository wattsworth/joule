from tests.api import mock_session
import tempfile
import unittest
import os
from joule.api.node import TcpNode
from joule.constants import EndPoints
from joule.utilities.archive_tools import ImportLogger

class TestArchiveApi(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self) -> None:
        # no URL or event loop
        self.node = TcpNode('mock_node', 'http://url', 'api_key')
        self.session = mock_session.MockSession()
        self.node.session = self.session

    async def test_archive_upload(self):
        # uploads an archive file
        self.session.response_data=ImportLogger().to_json()
        (fd,path) = tempfile.mkstemp()
        with open(fd,'w') as f:
            f.write("hello world")
        await self.node.archive_upload(path)
        self.assertEqual(self.session.path, EndPoints.archive)
        self.assertEqual(self.session.request_data, b"hello world")
        os.remove(path)