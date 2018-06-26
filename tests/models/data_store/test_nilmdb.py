import asynctest
import aiohttp
import asyncio
import numpy as np

from joule.models import Stream, Element
from joule.models.data_store.nilmdb import NilmdbStore
from joule.models.data_store.errors import InsufficientDecimationError, DataError
from .fake_nilmdb import FakeNilmdb, FakeResolver, FakeStream
from tests import helpers


class TestNilmdbStore(asynctest.TestCase):
    use_default_loop = False
    forbid_get_event_loop = True

    async def setUp(self):
        self.fake_nilmdb = FakeNilmdb(loop=self.loop)
        info = await self.fake_nilmdb.start()
        resolver = FakeResolver(info, loop=self.loop)
        connector = aiohttp.TCPConnector(loop=self.loop, resolver=resolver)
        url = "http://test.nodes.wattsworth.net:%d/nilmdb" % \
              info['test.nodes.wattsworth.net']
        # url = "http://localhost/nilmdb"
        self.store = NilmdbStore(url, 5, 60, self.loop)
        self.store.connector = connector

        # make a couple example streams
        # stream1 int8_3
        self.stream1 = Stream(id=1, name="stream1", datatype=Stream.DATATYPE.INT8,
                              elements=[Element(name="e%d" % x) for x in range(3)])

        # stream2 uint16_4
        self.stream2 = Stream(id=2, name="stream2", datatype=Stream.DATATYPE.UINT16,
                              elements=[Element(name="e%d" % x) for x in range(4)])

    async def tearDown(self):
        await self.fake_nilmdb.stop()
        self.store.close()

    async def test_initialize(self):

        await self.store.initialize([self.stream1, self.stream2])
        # can initialize streams multiple times
        await self.store.initialize([self.stream1])

        self.assertEqual(len(self.fake_nilmdb.posts), 3)
        self.assertEqual(len(self.fake_nilmdb.streams), 2)
        self.assertEqual(self.fake_nilmdb.streams["/joule/1"].layout, "int8_3")
        self.assertEqual(self.fake_nilmdb.streams["/joule/2"].layout, "uint16_4")

    async def test_insert(self):
        await self.store.initialize([self.stream1])
        nrows = 300
        data = helpers.create_data(layout="int8_3", length=nrows)
        # first insert
        await self.store.insert(self.stream1, data['timestamp'][0],
                                data['timestamp'][-1] + 1, data)
        self.assertEqual(self.fake_nilmdb.streams["/joule/1"].rows, nrows)
        # another insert
        data = helpers.create_data(layout="int8_3", start=data['timestamp'][-1] + 1,
                                   length=nrows)
        await self.store.insert(self.stream1, data['timestamp'][0],
                                data['timestamp'][-1] + 1, data)
        self.assertEqual(self.fake_nilmdb.streams["/joule/1"].rows, nrows * 2)

    async def test_decimating_inserter(self):
        self.stream1.decimate = True
        data_queue = asyncio.Queue()
        nrows = 955
        data = helpers.create_data(layout="int8_3", length=nrows)
        self.store.insert_period = 0.02
        task = self.store.spawn_inserter(self.stream1, data_queue, self.loop)
        for chunk in helpers.to_chunks(data, 300):
            await data_queue.put(chunk)
            await asyncio.sleep(0.05)
        await asyncio.sleep(0.05)
        task.cancel()
        await task
        self.assertTrue(len(self.fake_nilmdb.streams), 5)
        self.assertEqual(self.fake_nilmdb.streams["/joule/1"].rows, nrows)
        self.assertEqual(self.fake_nilmdb.streams["/joule/1~decim-4"].rows,
                         np.floor(nrows / 4))
        self.assertEqual(self.fake_nilmdb.streams["/joule/1~decim-16"].rows,
                         np.floor(nrows / 16))
        self.assertEqual(self.fake_nilmdb.streams["/joule/1~decim-64"].rows,
                         np.floor(nrows / 64))
        self.assertEqual(self.fake_nilmdb.streams["/joule/1~decim-256"].rows,
                         np.floor(nrows / 256))

    async def test_nondecimating_inserter(self):
        self.stream1.decimate = False
        self.stream1.datatype = Stream.DATATYPE.UINT16
        data_queue = asyncio.Queue()
        nrows = 896
        data = helpers.create_data(layout="uint16_3", length=nrows)
        self.store.insert_period = 0.02
        task = self.store.spawn_inserter(self.stream1, data_queue, self.loop)
        for chunk in helpers.to_chunks(data, 300):
            await data_queue.put(chunk)
            await asyncio.sleep(0.05)
        await asyncio.sleep(0.05)
        task.cancel()
        await task

        self.assertEqual(self.fake_nilmdb.streams["/joule/1"].rows, nrows)
        self.assertTrue(len(self.fake_nilmdb.streams), 1)

    async def test_extract(self):
        # initialize nilmdb state
        nrows = 1000
        self.fake_nilmdb.streams['/joule/1'] = FakeStream(
            layout=self.stream1.layout, start=100, end=1000, rows=nrows)
        self.fake_nilmdb.streams['/joule/1~decim-4'] = FakeStream(
            layout=self.stream1.decimated_layout, start=100, end=1000, rows=nrows // 4)
        self.fake_nilmdb.streams['/joule/1~decim-16'] = FakeStream(
            layout=self.stream1.decimated_layout, start=100, end=1000, rows=nrows // 16)
        self.fake_nilmdb.streams['/joule/1~decim-64'] = FakeStream(
            layout=self.stream1.decimated_layout, start=100, end=1000, rows=nrows // 64)
        data_queue = asyncio.Queue()

        # should return *raw* data when max_rows and decimation_level are None
        await self.store.extract(self.stream1, start=100, end=1000, output=data_queue)
        self.assertEqual(len(self.fake_nilmdb.extract_calls), 1)
        path = self.fake_nilmdb.extract_calls[0]['path']
        self.assertTrue(path, '/joule/1')
        rcvd_rows = 0
        while not data_queue.empty():
            chunk = await data_queue.get()
            if chunk is not None:
                rcvd_rows += len(chunk)
        self.assertEqual(nrows, rcvd_rows)

        # should return *decimated* data when max_rows!=None
        self.fake_nilmdb.extract_calls = []  # reset
        await self.store.extract(self.stream1, start=100, end=1000,
                                 output=data_queue, max_rows=int(1.5 * (nrows / 16)))
        # expect count req from raw and decim-16, and extract from data from decim-16
        self.assertEqual(len(self.fake_nilmdb.extract_calls), 3)
        path = self.fake_nilmdb.extract_calls[0]['path']
        self.assertTrue(path, '/joule/1~decim-16')
        rcvd_rows = 0
        while not data_queue.empty():
            chunk = await data_queue.get()
            if chunk is not None:
                rcvd_rows += len(chunk)
        self.assertEqual(nrows // 16, rcvd_rows)

        # should raise exception if data is not decimated enough
        with self.assertRaises(InsufficientDecimationError):
            await self.store.extract(self.stream1, start=100, end=1000,
                                     output=data_queue, max_rows=nrows // 128)

        # should return data from a specified decimation level
        self.fake_nilmdb.extract_calls = []  # reset
        await self.store.extract(self.stream1, start=100, end=1000,
                                 output=data_queue, decimation_level=64)
        # expect extract from decim-64
        self.assertEqual(len(self.fake_nilmdb.extract_calls), 1)
        path = self.fake_nilmdb.extract_calls[0]['path']
        self.assertTrue(path, '/joule/1~decim-64')
        rcvd_rows = 0
        while not data_queue.empty():
            chunk = await data_queue.get()
            if chunk is not None:
                rcvd_rows += len(chunk)
        self.assertEqual(nrows // 64, rcvd_rows)

        # if max_rows and decimation_level specified, error if
        # too much data
        with self.assertRaises(InsufficientDecimationError):
            await self.store.extract(self.stream1, start=100, end=1000,
                                     output=data_queue, decimation_level=64,
                                     max_rows=nrows // 128)

        # error if decimation_level does not exist
        with self.assertRaises(DataError):
            await self.store.extract(self.stream1, start=100, end=1000,
                                     output=data_queue, decimation_level=5)

    async def test_intervals(self):
        intervals = [[1, 2], [2, 3], [3, 4]]
        self.fake_nilmdb.streams['/joule/1'] = FakeStream(
            layout=self.stream1.layout, start=100, end=1000,
            intervals=intervals)
        rcvd_intervals = await self.store.intervals(self.stream1,
                                                    start=None,
                                                    end=None)
        self.assertEqual(intervals, rcvd_intervals)

        # handles empty intervals
        self.fake_nilmdb.streams['/joule/1'].intervals = None
        rcvd_intervals = await self.store.intervals(self.stream1,
                                                    start=None,
                                                    end=None)
        self.assertEqual([], rcvd_intervals)

    async def test_remove(self):
        # initialize nilmdb state
        self.fake_nilmdb.streams['/joule/1'] = FakeStream(
            layout=self.stream1.layout, start=1, end=100, rows=100)
        self.fake_nilmdb.streams['/joule/1~decim-4'] = FakeStream(
            layout=self.stream1.decimated_layout, start=1, end=100, rows=100)
        self.fake_nilmdb.streams['/joule/1~decim-16'] = FakeStream(
            layout=self.stream1.decimated_layout, start=1, end=100, rows=100)
        self.fake_nilmdb.streams['/joule/1~decim-64'] = FakeStream(
            layout=self.stream1.decimated_layout, start=1, end=100, rows=100)

        # removes data between time bounds at all decimation levels
        await self.store.remove(self.stream1, start=1, end=1000)
        self.assertEqual(len(self.fake_nilmdb.remove_calls), 4)
        paths = ['/joule/1', '/joule/1~decim-4',
                 '/joule/1~decim-16', '/joule/1~decim-64']
        for call in self.fake_nilmdb.remove_calls:
            self.assertTrue(call["path"] in paths)

    async def test_info(self):
        self.fake_nilmdb.streams['/joule/1'] = FakeStream(
            layout=self.stream1.layout, start=1, end=100, rows=200)
        info = await self.store.info(self.stream1)
        self.assertEqual(info.start, 1)
        self.assertEqual(info.end, 100)
        self.assertEqual(info.rows, 200)
