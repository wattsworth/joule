from aiohttp.test_utils import AioHTTPTestCase, unittest_run_loop
from aiohttp import web
from sqlalchemy.orm import Session
import asyncio
from joule.models import Follower
import joule.controllers
from joule.api.node.node_info import NodeInfo
from tests.controllers.helpers import create_db, MockStore
from joule import app_keys
from joule.constants import EndPoints
from unittest import mock
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
        app[app_keys.cafile] = "stubbed_cafile"
        app[app_keys.db], app[psql_key] = await asyncio.to_thread(lambda: create_db([]))
        app[app_keys.name] = "test-node"
        return app


    async def test_lists_follower_nodes(self):
        db = self.app[app_keys.db]
        follower1 = Follower(name="test-follower",key="key1",location="http://othernode.local:8080")
        follower2 = Follower(name="test-follower2",key="key2",location="http://othernode2.local:8080")
        db.add(follower1)
        db.add(follower2)
        self.assertEqual(db.query(Follower).count(),2)
        resp = await self.client.get(EndPoints.followers)
        self.assertEqual(resp.status, 200)
        data = await resp.json()
        self.assertEqual(len(data),2)
        self.assertIn(follower1.to_json(),data)
        self.assertIn(follower2.to_json(),data)

    @mock.patch('joule.controllers.follower_controller.TcpNode', )
    async def test_adds_follower_node(self, mock_node_class):
        mock_node = mock.AsyncMock()
        mock_node.info.return_value = NodeInfo(version="1.0",name="test-node-follower",path="/path",
                                               size_reserved=0,size_other=0,size_free=0,size_db=0)
        mock_node_class.return_value = mock_node
        # patch the TcpNode class to return a mock object
        resp = await self.client.post(EndPoints.follower, 
                                      json={"key":"key",
                                            "port":8080,
                                            "scheme":"http",
                                            "base_uri":"/endpoint"})
        # Follower's request is successful and gets *this* node's name
        self.assertEqual(resp.status, 200)
        data = await resp.json()
        self.assertEqual(data['name'],"test-node")
        # Follower is added to the database
        db = self.app[app_keys.db]
        self.assertEqual(db.query(Follower).count(),1)
        follower = db.query(Follower).one()
        self.assertEqual(follower.name,"test-node-follower")
        self.assertEqual(follower.key,"key")
        # follower's IP address is based on request.remote which is just localhost
        self.assertEqual(follower.location,"http://127.0.0.1:8080/endpoint")
        # drop the follower from the database
        db.query(Follower).delete()

        # Follower can specify it's own name which will be used in place of the 
        # request.remote IP address
        resp = await self.client.post(EndPoints.follower, 
                                      json={"key":"key",
                                            "port":8080,
                                            "scheme":"https",
                                            "base_uri":"",
                                            "name": "follower-node",
                                            "name_is_host":True})
        self.assertEqual(resp.status, 200)
        data = await resp.json()
        self.assertEqual(data['name'],"test-node")

        db = self.app[app_keys.db]
        self.assertEqual(db.query(Follower).count(),1)
        follower = db.query(Follower).one()
        self.assertEqual(follower.name,"test-node-follower")
        self.assertEqual(follower.key,"key")
        self.assertEqual(follower.location,"https://follower-node:8080")

    async def test_deletes_follower_nodes(self):
        db = self.app[app_keys.db]
        db.add(Follower(name="test-follower",key="key",location="http://othernode.local:8080"))
        self.assertEqual(db.query(Follower).count(),1)
        resp = await self.client.delete(EndPoints.follower,params={"name":"test-follower"})
        self.assertEqual(resp.status, 200)
        # the follower should be removed
        self.assertEqual(db.query(Follower).count(),0)
