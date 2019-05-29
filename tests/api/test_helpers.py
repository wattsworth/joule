from tests.api import mock_session
import asynctest
import tempfile
import os

from joule.api import helpers


class TestApiHelpers(asynctest.TestCase):

    async def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        os.environ["JOULE_USER_CONFIG_DIR"] = self.temp_dir.name

    async def tearDown(self):
        self.temp_dir.cleanup()

    async def test_creates_config_dir(self):
        # require helper to create the directory
        config_dir = os.path.join(self.temp_dir.name, "configs")
        os.environ["JOULE_USER_CONFIG_DIR"] = config_dir
        helpers.get_nodes()
        self.assertTrue(os.path.isdir(config_dir))
