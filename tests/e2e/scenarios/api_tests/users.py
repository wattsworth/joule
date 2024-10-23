import unittest
import sqlalchemy
import numpy as np
from joule import api, errors
from joule.utilities import datetime_to_timestamp as dt2ts

class TestUserMethods(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self):
        self.node = api.get_node()

    async def asyncTearDown(self) -> None:
        await self.node.close()

    async def test_master_list(self):
        masters = await self.node.master_list()
        master_names = [m.name for m in masters]
        # e2e is created by admin authorize and auto_user is created by the user file
        # in main_node.py
        self.assertListEqual(master_names, ['e2e', 'auto_user'])


    