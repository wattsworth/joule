from aiohttp.test_utils import AioHTTPTestCase
from aiohttp import web
import aiohttp
import os
import tempfile
import hashlib
import shutil
import aiofiles
import joule.app_keys
import joule.controllers
import joule.middleware
import asyncio
from joule.models.data_movement.importing.importer_manager import ImporterManager
import testing.postgresql
from unittest import mock
from joule.utilities.archive_tools import ImportLogger

from joule.models import Master
from joule.constants import EndPoints
from tests.controllers.helpers import create_db

TEST_ARCHIVE = os.path.join(os.path.dirname(__file__), '../cli/archive/archives/ww-data_2025_09_03-10-03-59.zip')
IMPORTER_API_KEY = 'test-importer-api-key'
psql_key = web.AppKey("psql", testing.postgresql.Postgresql)

class TestArchiveController(AioHTTPTestCase):

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
        app[joule.app_keys.uploaded_archives_dir]  = self.archive_directory
        self.mock_manager = mock.MagicMock(spec=ImporterManager)
        self.mock_manager.process_archive = mock.AsyncMock(return_value=ImportLogger()) # mock the results message list
        app[joule.app_keys.importer_manager] = self.mock_manager
        return app
    
    async def test_upload_archive_file(self):
       
        # upload an archive file
        async with aiofiles.open(TEST_ARCHIVE,'rb') as f:
            resp: aiohttp.ClientResponse = await \
                self.client.post(EndPoints.archive, data=f,
                                 headers={'X-API-KEY':'test-user-api-key'})
        # print the response text if the test fails
        if resp.status != 200:
            print(await resp.text())
        self.assertEqual(resp.status, 200)
        # check that the file was processed
        self.mock_manager.process_archive.assert_called_once()
        # make sure the file got uploaded correctly
        uploaded_file = self.mock_manager.process_archive.call_args.kwargs['archive_path']
        async with (aiofiles.open(uploaded_file,'rb') as uploaded_data,
              aiofiles.open(TEST_ARCHIVE,'rb') as orig_data):
            self.assertEqual(hashlib.md5(await orig_data.read()).hexdigest(), 
                             hashlib.md5(await uploaded_data.read()).hexdigest())
            
        # do the same test with the importer API key for authentication
        self.mock_manager.reset_mock()
        async with aiofiles.open(TEST_ARCHIVE,'rb') as f:
            resp: aiohttp.ClientResponse = await \
                self.client.post(EndPoints.archive, data=f,
                                 headers={'X-API-KEY':'test-importer-api-key'})
        # print the response text if the test fails
        if resp.status != 200:
            print(await resp.text())
        self.assertEqual(resp.status, 200)
        # check that the file was processed
        self.mock_manager.process_archive.assert_called_once()
        # make sure the file got uploaded correctly
        uploaded_file = self.mock_manager.process_archive.call_args.kwargs['archive_path']
        async with (aiofiles.open(uploaded_file,'rb') as uploaded_data,
              aiofiles.open(TEST_ARCHIVE,'rb') as orig_data):
            self.assertEqual(hashlib.md5(await orig_data.read()).hexdigest(), 
                             hashlib.md5(await uploaded_data.read()).hexdigest())
