from aiohttp.test_utils import unused_port
import os
import warnings
import unittest

from joule.models import DataStream, Element, pipes
from joule.models.data_store.nilmdb import NilmdbStore, bytes_per_row
from joule.models.data_store.errors import InsufficientDecimationError, DataError
from tests.models.data_store.fake_nilmdb import FakeNilmdb, FakeStream
from tests import helpers

STREAM_LIST = os.path.join(os.path.dirname(__file__), 'stream_list.json')
warnings.simplefilter('always')


class TestNilmdbStore(unittest.IsolatedAsyncioTestCase):
    use_default_loop = False
    forbid_get_event_loop = True

    async def asyncSetUp(self):
        self.fake_nilmdb = FakeNilmdb()
        url = await self.fake_nilmdb.start()

        # use a 0 insert period for test execution
        self.store = NilmdbStore(url, 0, 60)

        # make a couple example streams
        # stream1 int8_3
        self.stream1 = DataStream(id=1, name="stream1", datatype=DataStream.DATATYPE.INT8,
                                  elements=[Element(name="e%d" % x) for x in range(3)])

        # stream2 uint16_4
        self.stream2 = DataStream(id=2, name="stream2", datatype=DataStream.DATATYPE.UINT16,
                                  elements=[Element(name="e%d" % x) for x in range(4)])

    async def asyncTearDown(self) -> None:
        await self.fake_nilmdb.stop()
        await self.store.close()

    async def test_initialize(self):

        await self.store.initialize([self.stream1, self.stream2])
        await self.store.close()
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
        await self.store.close()
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

    async def test_extract(self):
        await self.store.initialize([])
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
        self.assertEqual(nrows, rcvd_rows)

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
        self.assertEqual(nrows // 16, rcvd_rows)

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
        self.assertEqual(nrows // 64, rcvd_rows)

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

    async def test_extract_empty_data(self):
        await self.store.initialize([])
        # initialize nilmdb state
        self.fake_nilmdb.streams['/joule/1'] = FakeStream(
            layout=self.stream1.layout, start=100, end=1000, rows=0)

        async def callback(data, layout, decimation_factor):
            self.assertEqual(decimation_factor, 1)
            self.assertEqual(self.stream1.layout, layout)
            self.assertEqual(pipes.compute_dtype(self.stream1.layout), data.dtype)
            if len(data) == 0:
                self.assertEqual(0, len(data['timestamp']))
            else:
                for row in data:
                    self.assertEqual(row, pipes.interval_token(self.stream1.layout))

        # should return empty data with the correct type when there is no data
        await self.store.extract(self.stream1, start=100, end=1000, max_rows=100, callback=callback)
        await self.store.extract(self.stream1, start=100, end=1000, callback=callback)
        await self.store.extract(self.stream1, start=100, end=1000, callback=callback)

    async def test_extract_errors(self):
        await self.store.initialize([])
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
                                     max_rows=(nrows // 4 - 10))
        self.assertTrue('empty' in str(e.exception))

    async def test_intervals(self):
        await self.store.initialize([])
        actual_intervals = [[1, 5],
                            [10, 15], [15, 18], [18, 20],
                            [30, 31], [31, 40]]
        consolidated_intervals = [[1, 5], [10, 20], [30, 40]]
        self.fake_nilmdb.streams['/joule/1'] = FakeStream(
            layout=self.stream1.layout, start=100, end=1000,
            intervals=actual_intervals)
        rcvd_intervals = await self.store.intervals(self.stream1,
                                                    start=None,
                                                    end=None)
        self.assertEqual(consolidated_intervals, rcvd_intervals)

        # handles empty intervals
        self.fake_nilmdb.streams['/joule/1'].intervals = None
        rcvd_intervals = await self.store.intervals(self.stream1,
                                                    start=None,
                                                    end=None)
        self.assertEqual([], rcvd_intervals)

        # ignore 404 error if stream does not exist (return empty interval)
        new_stream = helpers.create_stream("new", "float32_3", id=100)
        rcvd_intervals = await self.store.intervals(new_stream,
                                                    start=None,
                                                    end=None)
        self.assertEqual([], rcvd_intervals)

        # propogate any other error
        self.fake_nilmdb.stub_stream_intervals = True
        self.fake_nilmdb.response = 'notjson'
        self.fake_nilmdb.http_code = 500
        with self.assertRaises(DataError):
            await self.store.intervals(self.stream1,
                                       start=None,
                                       end=None)

    async def test_remove(self):
        await self.store.initialize([])
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
        await self.store.initialize([])
        with open(STREAM_LIST, 'r') as f:
            self.fake_nilmdb.stream_list_response = f.read()
        streams = [helpers.create_stream('S%d' % x, 'float32_3', id=x) for x in range(8)]
        info = await self.store.info(streams)
        # streams 1, 2, 6, 7, 8 are in the json file but 8 is not in the streams request
        for stream_id in [1, 2, 6, 7]:
            self.assertTrue(stream_id in info)
        # S1 should be empty
        s1_info = info[1]
        self.assertIsNone(s1_info.start)
        self.assertIsNone(s1_info.end)
        self.assertEqual(s1_info.rows, 0)
        self.assertEqual(s1_info.bytes, 0)
        # S2 should have the following values
        s2_info = info[2]
        self.assertEqual(s2_info.start, 10)
        self.assertEqual(s2_info.end, 100)
        self.assertEqual(s2_info.rows, 64)
        self.assertEqual(s2_info.bytes, 1628)
        self.assertEqual(s2_info.total_time, 100)

    async def test_bytes_per_row(self):
        await self.store.initialize([])
        examples = [['float32_8', 40],
                    ['uint8_1', 9],
                    ['int16_20', 48],
                    ['float64_1', 16]]
        for example in examples:
            self.assertEqual(bytes_per_row(example[0]), example[1])
        bad_layouts = ['float32', '', 'abc', 'other32_8']
        for layout in bad_layouts:
            with self.assertRaises(ValueError) as e:
                bytes_per_row(layout)
            self.assertTrue(layout in str(e.exception))

    async def test_dbinfo(self):
        await self.store.initialize([])
        dbinfo = await self.store.dbinfo()
        # constants in fake_nilmdb
        self.assertEqual(dbinfo.path, '/opt/data')
        self.assertEqual(dbinfo.free, 178200829952)

    async def test_destroy(self):
        await self.store.initialize([])
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
