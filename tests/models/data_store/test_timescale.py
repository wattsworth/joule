import asynctest
import aiohttp
from aiohttp.test_utils import unused_port
import os
import warnings
import itertools
import psycopg2

from joule.models import Stream, Element, pipes
from joule.models.data_store import timescale
from tests import helpers

STREAM_LIST = os.path.join(os.path.dirname(__file__), 'stream_list.json')
warnings.simplefilter('always')


class TestTimescaleStore(asynctest.TestCase):
    use_default_loop = False
    forbid_get_event_loop = True

    async def setUp(self):
        self.dsn = "postgres://tester:tester@172.16.1.12:5432/tester"

        # use a 0 insert period for test execution
        self.store = timescale.TimescaleStore(self.dsn, 0, 60, self.loop)

        # make a couple example streams
        # stream1 int8_3
        self.stream1 = Stream(id=1, name="stream1", datatype=Stream.DATATYPE.INT8,
                              elements=[Element(name="e%d" % x) for x in range(3)])

        # stream2 uint16_4
        self.stream2 = Stream(id=2, name="stream2", datatype=Stream.DATATYPE.FLOAT32,
                              elements=[Element(name="e%d" % x) for x in range(4)])
        self.conn = psycopg2.connect(dsn=self.dsn)
        self.curs = self.conn.cursor()
        for stream in [self.stream1, self.stream2]:
            self.curs.execute("DROP TABLE IF EXISTS stream%d"%stream.id)
            self.curs.execute("DROP TABLE IF EXISTS stream%d_intervals"%stream.id)
        self.conn.commit()


    async def tearDown(self):
        await self.store.close()

    async def test_initialize(self):

        await self.store.initialize([self.stream1, self.stream2])
        # can initialize streams multiple times
        await self.store.initialize([self.stream1])

        # verify the tables are created
        self.curs.execute('''SELECT table_name FROM information_schema.tables 
                                     WHERE table_schema='public';''')
        tables = list(itertools.chain(*(self.curs.fetchall())))
        for table in ['stream1', 'stream1_intervals',
                      'stream2', 'stream2_intervals']:
            self.assertIn(table, tables)

        # check the column data types
        self.curs.execute('''SELECT column_name, data_type FROM information_schema.columns 
                                             WHERE table_name='stream2';''')
        cols = self.curs.fetchall()
        (names, types) = zip(*cols)
        self.assertCountEqual(names, ['time','elem0','elem1','elem2','elem3'])
        self.assertEqual(types,('timestamp without time zone',
                                'real','real','real','real'))
        self.assertEqual(len(cols), 5)


