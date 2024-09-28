from aiohttp.test_utils import AioHTTPTestCase, unittest_run_loop
from aiohttp import web
from sqlalchemy.orm import Session
import asyncio
from unittest import mock
from joule.models import master, Master
import joule.controllers
from tests.controllers.helpers import create_db, MockStore
from joule import app_keys
from joule.constants import EndPoints

import testing.postgresql
psql_key = web.AppKey("psql", testing.postgresql.Postgresql)

class TestMasterController(AioHTTPTestCase):

    async def tearDownAsync(self):
        self.app[app_keys.db].close()
        await asyncio.to_thread(self.app[psql_key].stop)
        await self.client.close()

    async def get_application(self):
        app = web.Application()
        app.add_routes(joule.controllers.routes)
        # this takes a while, adjust the expected coroutine execution time
        loop = asyncio.get_running_loop()
        loop.slow_callback_duration = 2.0

        app[app_keys.db], app[psql_key] = await asyncio.to_thread(lambda: create_db([]))
        app[app_keys.data_store] = MockStore()
        app[app_keys.name] = "test"
        app[app_keys.port] = 443
        app[app_keys.scheme] = "http"
        app[app_keys.base_uri] = "/"
        app[app_keys.cafile] = "stubbed_cafile"

        # create a master user to grant access
        self.grantor = Master(name="grantor", key="grantor_key",
                              type=Master.TYPE.USER)
        app[app_keys.db].add(self.grantor)
        app[app_keys.db].commit()
        return app


    async def test_adds_master_user(self):
        db: Session = self.app[app_keys.db]
        # add user to johndoe
        payload = {
            "master_type": "user",
            "identifier": "johndoe"
        }
        resp = await self.client.post(EndPoints.master, json=payload,
                                      headers={'X-API-KEY': "grantor_key"})
        self.assertEqual(resp.status, 200)
        json = await resp.json()
        m = db.query(Master).filter(Master.name == "johndoe").one_or_none()
        self.assertEqual(m.grantor_id, self.grantor.id)
        self.assertEqual(json['key'], m.key)

        # adding johndoe again returns an error and does not change the key
        resp = await self.client.post(EndPoints.master, json=payload,
                                      headers={'X-API-KEY': "grantor_key"})
        old_key = m.key
        m = db.query(Master).filter(Master.name == "johndoe").one_or_none()
        new_key = m.key
        self.assertEqual(old_key, new_key)
        self.assertEqual(resp.status, 400)


    @mock.patch('joule.controllers.master_controller.TcpSession')
    @mock.patch('joule.controllers.master_controller.detect_url')
    async def test_adds_master_joule(self, detect_url, mock_session_class):
        mock_session = mock.AsyncMock()
        mock_session_class.return_value = mock_session
        # mock the post coroutine to return the expected JSON data
        mock_session.post.return_value = {"name": "joule_master_node"}

        db: Session = self.app[app_keys.db]
        # add joule node
        payload = {
            "master_type": "joule",
            "identifier": "http://master_node",
        }
        resp = await self.client.post(EndPoints.master, json=payload,
                                        headers={'X-API-KEY': "grantor_key"})
        # check the response
        self.assertEqual(resp.status, 200)
        data = await resp.json()
        # make sure the database entry is created
        self.assertEqual(db.query(Master).filter(Master.name == "joule_master_node").count(),1)
        self.assertEqual(data['name'], "joule_master_node")
        # make sure the other node received the correct data
        mock_session.post.assert_called_once()
        self.assertEqual(mock_session.post.call_args[0][0], EndPoints.follower)
        params = mock_session.post.call_args[1]['json']
        self.assertIn('key', params)
        self.assertEqual(params['port'], self.app[app_keys.port])
        self.assertEqual(params['scheme'], self.app[app_keys.scheme])
        self.assertEqual(params['base_uri'], self.app[app_keys.base_uri])
        self.assertEqual(params['name'], "test")

        # if the master is not specified with a URL, try to create one
        detect_url.return_value = "https://master_node"
        payload = {
            "master_type": "joule",
            "identifier": "master_node",
        }
        resp = await self.client.post(EndPoints.master, json=payload,
                                        headers={'X-API-KEY': "grantor_key"})
        self.assertEqual(resp.status, 200)
        mock_session_class.call_count = 2
        self.assertEqual("https://master_node",mock_session_class.call_args[0][0])

    @mock.patch('joule.controllers.master_controller.TcpSession')
    @mock.patch('joule.controllers.master_controller.detect_url')
    async def test_adds_master_lumen(self, detect_url, mock_session_class):
        mock_session = mock.AsyncMock()
        mock_session_class.return_value = mock_session
        # mock the post coroutine to return the expected JSON data
        mock_session.post.return_value = {"name": "lumen_master_node"}

        db: Session = self.app[app_keys.db]
        # add joule node
        payload = {
            "master_type": "lumen",
            "identifier": "http://master_node",
            "lumen_params":{"key":"stubbed"}
        }
        resp = await self.client.post(EndPoints.master, json=payload,
                                        headers={'X-API-KEY': "grantor_key"})
        # check the response
        self.assertEqual(resp.status, 200)
        data = await resp.json()
        # make sure the database entry is created
        self.assertEqual(db.query(Master).filter(Master.name == "http://master_node").count(),1)
        self.assertEqual(data['name'], "http://master_node")
        # make sure the lumen node received the correct data
        mock_session.post.assert_called_once()
        self.assertEqual(mock_session.post.call_args[0][0], "/nilms.json")
        params = mock_session.post.call_args[1]['json']
        self.assertIn('key', params)
        self.assertEqual(params['port'], self.app[app_keys.port])
        self.assertEqual(params['scheme'], self.app[app_keys.scheme])
        self.assertEqual(params['base_uri'], self.app[app_keys.base_uri])
        self.assertEqual(params['name'], "test")

        # if the master is not specified with a URL, try to create one
        detect_url.return_value = "https://master_node"
        payload = {
            "master_type": "lumen",
            "identifier": "master_node",
            "lumen_params":{"key":"stubbed"}
        }
        resp = await self.client.post(EndPoints.master, json=payload,
                                        headers={'X-API-KEY': "grantor_key"})
        self.assertEqual(resp.status, 200)
        mock_session_class.call_count = 2
        self.assertEqual("https://master_node",mock_session_class.call_args[0][0])


    async def test_removes_master_user(self):
        db: Session = self.app[app_keys.db]
        db.add(Master(name="johndoe", key=master.make_key(), type=Master.TYPE.USER))
        db.commit()
        m = db.query(Master).filter(Master.name == "johndoe").one_or_none()
        self.assertIsNotNone(m)

        # can remove users
        payload = {
            "master_type": "user",
            "name": "johndoe"
        }
        resp = await self.client.delete(EndPoints.master, params=payload,
                                        headers={'X-API-KEY': "grantor_key"})
        self.assertEqual(resp.status, 200)
        m = db.query(Master).filter(Master.name == "johndoe").one_or_none()
        self.assertIsNone(m)

        # can remove nodes
        db.add(Master(name="joule", key=master.make_key(), type=Master.TYPE.JOULE_NODE))
        db.commit()
        m = db.query(Master).filter(Master.name == "joule").one_or_none()
        self.assertIsNotNone(m)
        payload = {
            "master_type": "joule",
            "name": "joule"
        }
        resp = await self.client.delete(EndPoints.master, params=payload,
                                        headers={'X-API-KEY': "grantor_key"})
        self.assertEqual(resp.status, 200)
        m = db.query(Master).filter(Master.name == "joule").one_or_none()
        self.assertIsNone(m)


    async def test_lists_masters(self):
        db: Session = self.app[app_keys.db]
        db.add(Master(name="johndoe", key=master.make_key(), type=Master.TYPE.USER))
        db.add(Master(name="joule", key=master.make_key(), type=Master.TYPE.JOULE_NODE))
        db.add(Master(name="lumen", key=master.make_key(), type=Master.TYPE.LUMEN_NODE))
        db.commit()

        resp = await self.client.get(EndPoints.masters,
                                     headers={'X-API-KEY': "grantor_key"})
        self.assertEqual(resp.status, 200)
        json = await resp.json()
        # grantor is the original user
        self.assertEqual(len(json), 4)
        for item in json:
            self.assertNotIn("key", item)
            self.assertIn(item["name"], ["johndoe", "joule", "lumen", "grantor"])
