import unittest
import sqlalchemy
from joule import api, errors


class TestDbMethods(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self):
        self.node = api.get_node()

    async def asyncTearDown(self) -> None:
        await self.node.close()
    @unittest.skip("skipping")
    async def test_db_connect(self):
        engine = await self.node.db_connect()
        with engine.connect() as con:
            result = con.execute(sqlalchemy.text("SELECT 1"))
            row = result.fetchone()
            self.assertEqual(row[0], 1)

    async def test_db_connection_info(self):
        conn_info = await self.node.db_connection_info()
        engine = sqlalchemy.create_engine(conn_info.to_dsn())
        with engine.connect() as con:
            result = con.execute(sqlalchemy.text("SELECT 1"))
            row = result.fetchone()
            self.assertEqual(row[0], 1)

    