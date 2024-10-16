import unittest
from joule import api, errors
from constants import *

class TestBackupIngestCopy(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self):
        self.node = api.get_node()
        """
        └── original
            ├── stream1
            └── stream2
            └── events
        """
        
    async def asyncTearDown(self):
        await self.node.close()

    async def test_backup_ingest(self):
        self.assertTrue(True)
        print("here!")
        print(t1)