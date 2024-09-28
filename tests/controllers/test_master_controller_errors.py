from aiohttp.test_utils import AioHTTPTestCase, unittest_run_loop
from aiohttp import web
from sqlalchemy.orm import Session
import asyncio
from unittest.mock import patch
from joule.models import master, Master
import joule.controllers
from tests.controllers.helpers import create_db, MockStore
from joule import app_keys
from joule.constants import EndPoints

import testing.postgresql
psql_key = web.AppKey("psql", testing.postgresql.Postgresql)

class TestMasterControllerErrors(AioHTTPTestCase):

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
        # must specify a valid master type
        payload = {
            "master_type": "invalid",
            "identifier": "johndoe"
        }
        resp = await self.client.post(EndPoints.master, json=payload,
                                      headers={'X-API-KEY': "grantor_key"})
        self.assertEqual(resp.status, 400)
        self.assertIn('master_type', await resp.text())

        # master_type must be in request
        payload = {
            "identifier": "johndoe"
        }
        resp = await self.client.post(EndPoints.master, json=payload,
                                      headers={'X-API-KEY': "grantor_key"})
        self.assertEqual(resp.status, 400)
        self.assertIn('master_type', await resp.text())

        # identifier must be in request
        payload = {
            "master_type": "joule"
        }
        resp = await self.client.post(EndPoints.master, json=payload,
                                      headers={'X-API-KEY': "grantor_key"})
        self.assertEqual(resp.status, 400)
        self.assertIn('identifier', await resp.text())

        # if an API key is specified it must be long enough
        payload = {
            "master_type": "user",
            "identifier": "johndoe",
            "api_key": "short"
        }
        resp = await self.client.post(EndPoints.master, json=payload,
                                      headers={'X-API-KEY': "grantor_key"})
        self.assertEqual(resp.status, 400)
        self.assertIn('API Key', await resp.text())

        # if the identifier is not a URL and cannot be turned into one
        # the request should fail
        with patch('joule.controllers.master_controller.detect_url') as mock_detect_url:
            mock_detect_url.return_value = None
            # For joule nodes...
            payload = {
                "master_type": "joule",
                "identifier": "invalid"
            }
            resp = await self.client.post(EndPoints.master, json=payload,
                                          headers={'X-API-KEY': "grantor_key"})
            self.assertEqual(resp.status, 400)
            self.assertIn('cannot connect', await resp.text())
            # For lumen nodes...
            payload = {
                "master_type": "lumen",
                "identifier": "invalid",
                "lumen_params": {"key": "stubbed"}
            }
            resp = await self.client.post(EndPoints.master, json=payload,
                                          headers={'X-API-KEY': "grantor_key"})
            self.assertEqual(resp.status, 400)
            self.assertIn('cannot connect', await resp.text())

    async def test_master_controller_delete_errors(self):
        # cannot delete yourself
        payload = {
            "master_type": "user",
            "name": "grantor"
        }
        resp = await self.client.delete(EndPoints.master, params=payload,
                                        headers={'X-API-KEY': "grantor_key"})
        self.assertEqual(resp.status, 400)
        self.assertIn('cannot delete yourself', await resp.text())

        # must specify a name and master_type
        payload = {
            "name": "johndoe"
        }
        resp = await self.client.delete(EndPoints.master, params=payload,
                                        headers={'X-API-KEY': "grantor_key"})
        self.assertEqual(resp.status, 400)
        self.assertIn('master_type', await resp.text())

        # master must exist
        payload = {
            "master_type": "user",
            "name": "not-present"
        }
        resp = await self.client.delete(EndPoints.master, params=payload,
                                        headers={'X-API-KEY': "grantor_key"})
        self.assertEqual(resp.status, 404)
        self.assertIn('not a master', await resp.text())