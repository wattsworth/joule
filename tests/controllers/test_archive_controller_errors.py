from aiohttp.test_utils import AioHTTPTestCase
from aiohttp import web
import aiohttp
import os
import tempfile
import hashlib
import shutil
import joule.app_keys
import joule.controllers
import joule.middleware
import asyncio
import testing.postgresql

from joule.models import Master
from joule.constants import EndPoints
from tests.controllers.helpers import create_db

TEST_ARCHIVE = os.path.join(os.path.dirname(__file__), '../cli/archive/archives/ww-data_2025_09_03-10-03-59.zip')
IMPORTER_API_KEY = 'test-importer-api-key'
psql_key = web.AppKey("psql", testing.postgresql.Postgresql)

class TestArchiveControllerErrors(AioHTTPTestCase):

    async def tearDownAsync(self):
        await self.client.close()
        shutil.rmtree(self.archive_directory)

    async def get_application(self):
         # start the API server
        middlewares = [
            joule.middleware.authorize(
                exemptions=joule.controllers.insecure_routes,
                route_specific_auth={('POST',joule.constants.EndPoints.archive): IMPORTER_API_KEY}
            )
        ]
        app = web.Application(middlewares=middlewares)
        app.add_routes(joule.controllers.routes)
        app[joule.app_keys.db], app[psql_key] = await asyncio.to_thread(lambda: create_db([]))
        # create a user to test access privileges
        self.user = Master(name="grantor", key="test-user-api-key", type=Master.TYPE.USER)
        app[joule.app_keys.db].add(self.user)
        app[joule.app_keys.db].commit()

        self.archive_directory = tempfile.mkdtemp()
        self.archive_list = []
        app[joule.app_keys.uploaded_archives_dir]  = self.archive_directory
        
        return app
    
    async def test_upload_requires_valid_api_key(self):
        self.assertEqual(len(self.archive_list),0)
        with open(TEST_ARCHIVE,'rb') as f:
            resp: aiohttp.ClientResponse = await \
                self.client.post(EndPoints.archive, data=f,
                                 headers={'X-API-KEY':'invalid-user-api-key'})
        # print the response text if the test fails
        if resp.status != 403:
            print(await resp.text())
        self.assertEqual(resp.status, 403)
        # check that the file is not in the queue
        self.assertEqual(len(self.archive_list),0)
        # check that the file did not get uploaded
        self.assertEqual(len(os.listdir(self.archive_directory)),0)
       