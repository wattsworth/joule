import asynctest
import aiohttp
from aiohttp.test_utils import unused_port
import numpy as np
import time

from joule.models import Stream, Element, pipes
from joule.models.data_store.nilmdb import NilmdbStore
from joule.models.data_store.errors import InsufficientDecimationError, DataError
from .fake_nilmdb import FakeNilmdb, FakeResolver, FakeStream
from tests import helpers
from ..pipes.reader import QueueReader


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
        # use a 0 insert period for test execution
        self.store = NilmdbStore(url, 0, 60, self.loop)
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

    async def test_initialize_errors(self):
        # when nilmdb returns invalid error data
        self.fake_nilmdb.stub_stream_create = True
        self.fake_nilmdb.response = 'notjson'
        self.fake_nilmdb.http_code = 500

        with self.assertRaises(DataError) as e:
            await self.store.initialize([self.stream1, self.stream2])
        # when nilmdb server is not available
        self.store.server = 'http://localhost:%d' % unused_port()
        with self.assertRaises(DataError):
            await self.store.initialize([self.stream1, self.stream2])

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

    async def test_insert_error_on_overlapping_data(self):
        # when nilmdb server rejects the data (eg overlapping timestamps)
        await self.store.initialize([self.stream1])
        self.fake_nilmdb.streams['/joule/1'] = FakeStream(
            layout=self.stream1.layout, start=0, end=500, rows=500)
        data = helpers.create_data(layout="int8_3", start=25, step=1, length=20)
        with self.assertRaises(DataError)as e:
            await self.store.insert(self.stream1, 25, 1000, data)
        self.assertTrue('overlaps' in str(e.exception))

    async def test_decimating_inserter(self):
        self.stream1.decimate = True
        source = QueueReader()
        pipe = pipes.InputPipe(stream=self.stream1, reader=source)
        nrows = 955
        data = helpers.create_data(layout="int8_3", length=nrows)
        task = self.store.spawn_inserter(self.stream1, pipe, self.loop)
        for chunk in helpers.to_chunks(data, 300):
            await source.put(chunk.tostring())
        await task
        self.assertEqual(len(self.fake_nilmdb.streams), 6)
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
        source = QueueReader()
        pipe = pipes.InputPipe(stream=self.stream1, reader=source)
        nrows = 896
        data = helpers.create_data(layout="uint16_3", length=nrows)
        task = self.store.spawn_inserter(self.stream1, pipe, self.loop, insert_period=0)
        for chunk in helpers.to_chunks(data, 300):
            await source.put(chunk.tostring())
        await task

        self.assertEqual(self.fake_nilmdb.streams["/joule/1"].rows, nrows)
        self.assertEqual(len(self.fake_nilmdb.streams), 1)

    async def test_propogates_intervals_to_decimations(self):
        self.stream1.decimate = True
        source = QueueReader()
        pipe = pipes.InputPipe(stream=self.stream1, reader=source)
        # insert the following broken chunks of data
        # |----15*8----|-15-|-15-|-15-|-15-|  ==> raw (120 samples)
        # |-----30-----|-3--|--3-|--3-|--3-|  ==> x4  (27 samples)
        # |-----7------|                      ==> x16 (7 samples)
        # |-----1------|                      ==> x64 (1 sample
        n_chunks = 12
        for i in range(n_chunks):
            data = helpers.create_data(layout="int8_3", length=15, start=i * 1e6, step=1)
            await source.put(data.tostring())
            if i > 6:  # breaks in the 2nd half
                await source.put(pipes.interval_token("int8_3").tostring())
        task = self.store.spawn_inserter(self.stream1, pipe, self.loop, insert_period=0)
        await task
        # should have raw, x4, x16, x64, x256
        self.assertEqual(len(self.fake_nilmdb.streams), 5)
        self.assertEqual(self.fake_nilmdb.streams["/joule/1"].rows, n_chunks * 15)
        # x4 level should be missing data due to interval breaks
        self.assertEqual(self.fake_nilmdb.streams["/joule/1~decim-4"].rows, 42)
        # x16 level should have 7 sample (only from first part)
        self.assertEqual(self.fake_nilmdb.streams["/joule/1~decim-16"].rows, 7)
        # x64 level should have 1 sample
        self.assertEqual(self.fake_nilmdb.streams["/joule/1~decim-64"].rows, 1)
        # x256 level should be empty
        self.assertEqual(self.fake_nilmdb.streams["/joule/1~decim-256"].rows, 0)

    async def test_inserter_data_error(self):
        # when stream has invalid data (eg bad timestamps)
        self.stream1.datatype = Stream.DATATYPE.UINT16
        source = QueueReader()
        pipe = pipes.InputPipe(stream=self.stream1, reader=source)
        task = self.store.spawn_inserter(self.stream1, pipe, self.loop, insert_period=0)
        await source.put(helpers.create_data(layout="uint16_3").tostring())
        # when nilmdb server generates an error
        self.fake_nilmdb.generate_error_on_path("/joule/1", 400, "bad data")
        with self.assertRaises(DataError):
            await task

    async def test_inserter_when_nilmdb_is_not_available(self):
        # when nilmdb server is not available
        self.stream1.datatype = Stream.DATATYPE.UINT16
        source = QueueReader()
        await self.fake_nilmdb.stop()
        await source.put(helpers.create_data(layout="uint16_3").tostring())
        pipe = pipes.InputPipe(stream=self.stream1, reader=source)
        task = self.store.spawn_inserter(self.stream1, pipe, self.loop, insert_period=0)
        with self.assertRaises(DataError):
            await task

    async def test_inserter_clean(self):
        self.stream1.datatype = Stream.DATATYPE.UINT16
        self.stream1.keep_us = 24 * 60 * 60 * 1e6  # 1 day
        self.stream1.decimate = True

        source = QueueReader(delay=0.1)
        await source.put(helpers.create_data(layout="uint16_3").tostring())
        pipe = pipes.InputPipe(stream=self.stream1, reader=source)
        self.store.cleanup_period = 0
        task = self.store.spawn_inserter(self.stream1, pipe, self.loop, insert_period=0)
        await task

        self.assertTrue(len(self.fake_nilmdb.remove_calls) > 0)
        # make sure decimations have been removed too
        removed_paths = [x['path'] for x in self.fake_nilmdb.remove_calls]
        self.assertTrue('/joule/1' in removed_paths)
        self.assertTrue('/joule/1~decim-4' in removed_paths)
        self.assertTrue('/joule/1~decim-16' in removed_paths)
        # make sure nilmdb cleanup executed with correct parameters
        params = self.fake_nilmdb.remove_calls[-1]
        self.assertEqual(int(params['start']), 0)
        expected = int(time.time() * 1e6) - self.stream1.keep_us
        actual = int(params['end'])
        # should be within 0.1 second
        np.testing.assert_almost_equal(expected / 1e6, actual / 1e6, decimal=1)

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

        extracted_data = []

        async def callback(data, layout, decimated):
            extracted_data.append(data)

        # should return *raw* data when max_rows and decimation_level are None
        await self.store.extract(self.stream1, start=100, end=1000, callback=callback)
        self.assertEqual(len(self.fake_nilmdb.extract_calls), 1)
        path = self.fake_nilmdb.extract_calls[0]['path']
        self.assertTrue(path, '/joule/1')
        rcvd_rows = 0
        last_row = []
        for chunk in extracted_data:
            if chunk is not None:
                rcvd_rows += len(chunk)
                last_row = chunk[-1]
        self.assertEqual(last_row, pipes.interval_token(self.stream1.layout))
        self.assertEqual(nrows, rcvd_rows - 1)  # ignore the interval token

        # should return *decimated* data when max_rows!=None
        self.fake_nilmdb.extract_calls = []  # reset
        extracted_data = []
        await self.store.extract(self.stream1, start=100, end=1000,
                                 callback=callback, max_rows=int(1.5 * (nrows / 16)))
        # expect count req from raw and decim-16, and extract from data from decim-16
        self.assertEqual(len(self.fake_nilmdb.extract_calls), 3)
        path = self.fake_nilmdb.extract_calls[0]['path']
        self.assertTrue(path, '/joule/1~decim-16')
        rcvd_rows = 0
        last_row = []
        for chunk in extracted_data:
            if chunk is not None:
                rcvd_rows += len(chunk)
                last_row = chunk[-1]
        self.assertEqual(last_row, pipes.interval_token(self.stream1.decimated_layout))
        self.assertEqual(nrows // 16, rcvd_rows - 1)

        # should raise exception if data is not decimated enough
        with self.assertRaises(InsufficientDecimationError):
            await self.store.extract(self.stream1, start=100, end=1000,
                                     callback=callback, max_rows=nrows // 128)

        # should return data from a specified decimation level
        self.fake_nilmdb.extract_calls = []  # reset
        extracted_data = []
        await self.store.extract(self.stream1, start=100, end=1000,
                                 callback=callback, decimation_level=64)
        # expect extract from decim-64
        self.assertEqual(len(self.fake_nilmdb.extract_calls), 1)
        path = self.fake_nilmdb.extract_calls[0]['path']
        self.assertTrue(path, '/joule/1~decim-64')
        rcvd_rows = 0
        last_row = []
        for chunk in extracted_data:
            if chunk is not None:
                rcvd_rows += len(chunk)
                last_row = chunk[-1]
        self.assertEqual(last_row, pipes.interval_token(self.stream1.decimated_layout))
        self.assertEqual(nrows // 64, rcvd_rows - 1)

        # if max_rows and decimation_level specified, error if
        # too much data
        with self.assertRaises(InsufficientDecimationError):
            await self.store.extract(self.stream1, start=100, end=1000,
                                     callback=callback, decimation_level=64,
                                     max_rows=nrows // 128)

        # error if decimation_level does not exist
        with self.assertRaises(DataError):
            await self.store.extract(self.stream1, start=100, end=1000,
                                     callback=callback, decimation_level=5)

    async def test_extract_errors(self):
        # initialize nilmdb state
        nrows = 1000
        self.fake_nilmdb.streams['/joule/1'] = FakeStream(
            layout=self.stream1.layout, start=100, end=1000, rows=nrows)
        self.fake_nilmdb.streams['/joule/1~decim-4'] = FakeStream(
            layout=self.stream1.decimated_layout, start=100, end=1000, rows=nrows // 4)
        # level 16 has no data
        self.fake_nilmdb.streams['/joule/1~decim-16'] = FakeStream(
            layout=self.stream1.decimated_layout, start=100, end=1000, rows=0)

        extracted_data = []

        async def callback(data, layout, decimated):
            extracted_data.append(data)

        # returns error because required level is emptyF
        with self.assertRaises(InsufficientDecimationError) as e:
            await self.store.extract(self.stream1, start=100, end=1000, callback=callback,
                                     max_rows=(nrows//4 - 10))
        self.assertTrue('empty' in str(e.exception))

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

    async def test_dbinfo(self):
        dbinfo = await self.store.dbinfo()
        # constants in fake_nilmdb
        self.assertEqual(dbinfo.path, '/opt/data')
        self.assertEqual(dbinfo.free, 178200829952)

    async def test_destroy(self):
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
        await self.store.destroy(self.stream1)
        self.assertEqual(len(self.fake_nilmdb.remove_calls), 4)
        paths = ['/joule/1', '/joule/1~decim-4',
                 '/joule/1~decim-16', '/joule/1~decim-64']
        for call in self.fake_nilmdb.remove_calls:
            self.assertTrue(call["path"] in paths)
        # and destroys the stream
        for call in self.fake_nilmdb.destroy_calls:
            self.assertTrue(call["path"] in paths)
