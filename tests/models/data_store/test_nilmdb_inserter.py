import unittest
import numpy as np
import time
import asyncio

from joule.models import DataStream, Element, pipes
from joule.models.data_store.nilmdb import NilmdbStore
from joule.models.data_store.errors import DataError
from tests.models.data_store.fake_nilmdb import FakeNilmdb
from tests import helpers
from tests.models.pipes.reader import QueueReader


class TestNilmdbInserter(unittest.IsolatedAsyncioTestCase):
    use_default_loop = False
    forbid_get_event_loop = True

    async def asyncSetUp(self):
        self.fake_nilmdb = FakeNilmdb()
        url = await self.fake_nilmdb.start()
        # use a 0 insert period for test execution
        self.store = NilmdbStore(url, 0, 60)
        await self.store.initialize([])
        # make a couple example streams
        # stream1 int8_3
        self.stream1 = DataStream(id=1, name="stream1", datatype=DataStream.DATATYPE.INT8,
                                  elements=[Element(name="e%d" % x) for x in range(3)])

    async def asyncTearDown(self):
        await self.fake_nilmdb.stop()
        await self.store.close()

    async def test_decimating_inserter(self):
        self.stream1.decimate = True
        source = QueueReader()
        pipe = pipes.InputPipe(stream=self.stream1, reader=source)
        nrows = 955
        data = helpers.create_data(layout="int8_3", length=nrows)
        task = await self.store.spawn_inserter(self.stream1, pipe)
        for chunk in helpers.to_chunks(data, 300):
            await source.put(chunk.tobytes())
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
        self.stream1.datatype = DataStream.DATATYPE.UINT16
        source = QueueReader()
        pipe = pipes.InputPipe(stream=self.stream1, reader=source)
        nrows = 896
        data = helpers.create_data(layout="uint16_3", length=nrows)
        task = await self.store.spawn_inserter(self.stream1, pipe, insert_period=0)
        for chunk in helpers.to_chunks(data, 300):
            await source.put(chunk.tobytes())
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
            await source.put(data.tobytes())
            if i > 6:  # breaks in the 2nd half
                await source.put(pipes.interval_token("int8_3").tobytes())
        task = await  self.store.spawn_inserter(self.stream1, pipe, insert_period=0)
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
        self.stream1.datatype = DataStream.DATATYPE.UINT16
        source = QueueReader()
        pipe = pipes.InputPipe(stream=self.stream1, reader=source)
        task = await self.store.spawn_inserter(self.stream1, pipe, insert_period=0)
        await source.put(helpers.create_data(layout="uint16_3").tobytes())
        # when nilmdb server generates an error
        self.fake_nilmdb.generate_error_on_path("/joule/1", 400, "bad data")
        with self.assertRaises(DataError):
            await task

    async def test_retries_when_nilmdb_is_not_available(self):
        # when nilmdb server is not available the inserter should retry
        self.stream1.datatype = DataStream.DATATYPE.UINT16
        source = QueueReader()
        await self.fake_nilmdb.stop()
        await source.put(helpers.create_data(layout="uint16_3").tobytes())
        pipe = pipes.InputPipe(stream=self.stream1, reader=source)
        with self.assertLogs(level="WARNING") as logs:
            task = await self.store.spawn_inserter(self.stream1, pipe, retry_interval=0.05)
            await asyncio.sleep(0.1)
            task.cancel()
            await task
        self.assertTrue("retrying request" in ''.join(logs.output))

    async def test_inserter_clean(self):
        self.stream1.datatype = DataStream.DATATYPE.UINT16
        self.stream1.keep_us = 24 * 60 * 60 * 1e6  # 1 day
        self.stream1.decimate = True

        source = QueueReader(delay=0.1)
        await source.put(helpers.create_data(layout="uint16_3").tobytes())
        pipe = pipes.InputPipe(stream=self.stream1, reader=source)
        self.store.cleanup_period = 0
        task = await self.store.spawn_inserter(self.stream1, pipe, insert_period=0)
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
