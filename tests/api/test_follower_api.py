from tests.api import mock_session
import unittest
from joule.api.node import TcpNode


from joule.constants import EndPoints


class TestFollowerApi(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self):
        # no URL or event loop
        self.node = TcpNode('mock_node', 'http://url', 'api_key')
        self.session = mock_session.MockSession()
        self.node.session = self.session

    async def test_follower_delete_by_name(self):
        await self.node.follower_delete("follower")
        self.assertEqual(self.session.method, 'DELETE')
        self.assertEqual(self.session.path, EndPoints.follower)
        self.assertEqual(self.session.request_data, {'name': "follower"})

    async def test_follower_delete_by_object(self):       
        # can delete by node object
        follower = TcpNode('follower', 'http://url', 'api_key')
        await self.node.follower_delete(follower)
        self.assertEqual(self.session.method, 'DELETE')
        self.assertEqual(self.session.path, EndPoints.follower)
        self.assertEqual(self.session.request_data, {'name': "follower"})

    ## follower list is covered by CLI tests