from aiohttp.test_utils import AioHTTPTestCase, unittest_run_loop
from aiohttp import web
from sqlalchemy.orm import Session
import asyncio
from joule.models import master, Master
import joule.controllers
from tests.controllers.helpers import create_db, MockStore


class TestMasterController(AioHTTPTestCase):

    async def tearDownAsync(self):
        self.app["db"].close()
        self.app["psql"].stop()
        await self.client.close()

    async def get_application(self):
        app = web.Application()
        app.add_routes(joule.controllers.routes)
        # this takes a while, adjust the expected coroutine execution time
        loop = asyncio.get_running_loop()
        loop.slow_callback_duration = 2.0

        app["db"], app["psql"] = create_db([])
        app["data-store"] = MockStore()
        app["name"] = "test"
        app["port"] = 443
        app["scheme"] = "http"
        app["base_uri"] = "/"

        # create a master user to grant access
        self.grantor = Master(name="grantor", key="grantor_key",
                              type=Master.TYPE.USER)
        app["db"].add(self.grantor)
        app["db"].commit()
        return app


    async def test_adds_master_user(self):
        db: Session = self.app["db"]
        # add user to johndoe
        payload = {
            "master_type": "user",
            "identifier": "johndoe"
        }
        resp = await self.client.post("/master.json", json=payload,
                                      headers={'X-API-KEY': "grantor_key"})
        self.assertEqual(resp.status, 200)
        json = await resp.json()
        m = db.query(Master).filter(Master.name == "johndoe").one_or_none()
        self.assertEqual(m.grantor_id, self.grantor.id)
        self.assertEqual(json['key'], m.key)

        # adding johndoe again returns an error and does not change the key
        resp = await self.client.post("/master.json", json=payload,
                                      headers={'X-API-KEY': "grantor_key"})
        old_key = m.key
        m = db.query(Master).filter(Master.name == "johndoe").one_or_none()
        new_key = m.key
        self.assertEqual(old_key, new_key)
        self.assertEqual(resp.status, 400)


    async def test_removes_master_user(self):
        db: Session = self.app["db"]
        db.add(Master(name="johndoe", key=master.make_key(), type=Master.TYPE.USER))
        db.commit()
        m = db.query(Master).filter(Master.name == "johndoe").one_or_none()
        self.assertIsNotNone(m)

        payload = {
            "master_type": "user",
            "name": "johndoe"
        }
        resp = await self.client.delete("/master.json", params=payload,
                                        headers={'X-API-KEY': "grantor_key"})
        self.assertEqual(resp.status, 200)
        m = db.query(Master).filter(Master.name == "johndoe").one_or_none()
        self.assertIsNone(m)


    async def test_lists_masters(self):
        db: Session = self.app["db"]
        db.add(Master(name="johndoe", key=master.make_key(), type=Master.TYPE.USER))
        db.add(Master(name="joule", key=master.make_key(), type=Master.TYPE.JOULE_NODE))
        db.add(Master(name="lumen", key=master.make_key(), type=Master.TYPE.LUMEN_NODE))
        db.commit()

        resp = await self.client.get("/masters.json",
                                     headers={'X-API-KEY': "grantor_key"})
        self.assertEqual(resp.status, 200)
        json = await resp.json()
        # grantor is the original user
        self.assertEqual(len(json), 4)
        for item in json:
            self.assertTrue("key" not in item)
            self.assertTrue(item["name"] in ["johndoe", "joule", "lumen", "grantor"])
