from aiohttp.test_utils import AioHTTPTestCase, unittest_run_loop
from aiohttp import web
from sqlalchemy.orm import Session
import asyncio
from unittest import mock
from joule.api.node.node_info import NodeInfo
from joule.models import Follower
import joule.controllers
from tests.controllers.helpers import create_db, MockStore
from joule import app_keys
from joule.constants import EndPoints

import testing.postgresql
psql_key = web.AppKey("psql", testing.postgresql.Postgresql)

class TestFollowerController(AioHTTPTestCase):

    async def tearDownAsync(self):
        self.app[app_keys.db].close()
        await asyncio.to_thread(self.app[psql_key].stop)
        await self.client.close()

    async def get_application(self):
        app = web.Application()
        app.add_routes(joule.controllers.routes)
        app[app_keys.name] = "test-node"
        app[app_keys.cafile] = "stubbed_cafile"
        app[app_keys.db], app[psql_key] = await asyncio.to_thread(lambda: create_db([]))
        return app

    @mock.patch('joule.controllers.follower_controller.TcpNode')
    async def test_adds_follower_node(self, mock_node_class):
        mock_node = mock.AsyncMock()
        mock_node.info.return_value = NodeInfo(version="1.0",name="test-node-follower",path="/path",
                                               size_reserved=0,size_other=0,size_free=0,size_db=0)
        mock_node_class.return_value = mock_node
        # must send a JSON request
        resp = await self.client.post(EndPoints.follower, 
                                      params={"key":"key",
                                            "port":8080,
                                            "scheme":"http",
                                            "base_uri":"/endpoint"})
        self.assertEqual(resp.status, 400)
        self.assertIn('content-type', await resp.text())

        # must have all parameters in request
        resp = await self.client.post(EndPoints.follower, 
                                      json={"key":"key",
                                            "port":'8080',
                                            "scheme":"http"})
        self.assertEqual(resp.status, 400)
        self.assertIn('base_uri', await resp.text())

        # handles ValueErrors (not clear why this could happen- maybe an endpoint returns invalid JSON by coincidence?)
        # raise a ValueError on the info call
        mock_node.info.side_effect = ValueError("bad value")
        resp = await self.client.post(EndPoints.follower, 
                                      json={"key":"key",
                                            "port":'8080',
                                            "scheme":"http",
                                            "base_uri":"/endpoint"})
        self.assertEqual(resp.status, 400)

    async def test_adds_follower_node_network_errors(self):
        # parameters must have valid values
        resp = await self.client.post(EndPoints.follower, 
                                      json={"key":"key",
                                            "port":"9999",
                                            "scheme":"invalid",
                                            "base_uri":"/endpoint"})
        self.assertEqual(resp.status, 400)
        self.assertIn('no route', await resp.text())

    async def test_deletes_follower_nodes(self):
        db = self.app[app_keys.db]
        db.add(Follower(name="test-follower",key="key",location="http://othernode.local:8080"))
        self.assertEqual(db.query(Follower).count(),1)

        # name must be correct
        resp = await self.client.delete(EndPoints.follower,params={"name":"not-present"})
        self.assertEqual(resp.status, 404)
        # the follower should not be removed
        self.assertEqual(db.query(Follower).count(),1)

        # name must be specified
        resp = await self.client.delete(EndPoints.follower)
        self.assertEqual(resp.status, 400)
        # the follower should not be removed
        self.assertEqual(db.query(Follower).count(),1)
