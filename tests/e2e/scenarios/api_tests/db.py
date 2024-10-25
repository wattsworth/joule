import unittest
import sqlalchemy
import numpy as np
from joule import api, errors
from joule.utilities import datetime_to_timestamp as dt2ts

class TestDbMethods(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self):
        self.node = api.get_node()

    async def asyncTearDown(self) -> None:
        await self.node.close()

    async def test_db_connect(self):
        # should be able to read data streams from postgres
        engine = await self.node.db_connect()
        stream = await self.node.data_stream_get("/live/base")
        # compare the first row of data from Postgres to a pipe read
        with engine.connect() as conn:
            resp = conn.execute(sqlalchemy.text(f"SELECT time,elem0 from data.stream{stream.id} ORDER BY time ASC LIMIT 1"))
            row = resp.fetchone()
            sql_data = np.array([dt2ts(row[0]),row[1]])
       
        pipe = await self.node.data_read("/live/base")
        pipe_data = await pipe.read(flatten=True)
        await pipe.close()
        np.testing.assert_array_equal(sql_data, pipe_data[0])

    async def test_custom_module_schemas(self):
        # the base module requests schema basedata
        engine = await self.node.db_connect()
        import asyncio
        #while True:
        #    await asyncio.sleep(2)
        with engine.connect() as conn:
            # create a table with a name and value column in the basedata schema
            conn.execute(sqlalchemy.text("CREATE TABLE basedata.test (name TEXT, value FLOAT)"))
            # add, retrieve, and remove a row from the table
            conn.execute(sqlalchemy.text("INSERT INTO basedata.test (name,value) VALUES ('test',1.0)"))
            resp = conn.execute(sqlalchemy.text("SELECT name,value FROM basedata.test"))
            row = resp.fetchone()
            self.assertEqual(row[0], "test")
            self.assertEqual(row[1], 1.0)
            conn.execute(sqlalchemy.text("DELETE FROM basedata.test"))
            resp = conn.execute(sqlalchemy.text("SELECT COUNT(*) FROM basedata.test"))
            row = resp.fetchone()
            self.assertEqual(row[0], 0)
            conn.execute(sqlalchemy.text("DROP TABLE basedata.test"))

    async def test_db_connection_info(self):
        conn_info = await self.node.db_connection_info()
        engine = sqlalchemy.create_engine(conn_info.to_dsn())
        with engine.connect() as con:
            result = con.execute(sqlalchemy.text("SELECT 1"))
            row = result.fetchone()
            self.assertEqual(row[0], 1)

    