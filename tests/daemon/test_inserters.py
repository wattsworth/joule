"""
Test the inserter and decimator objects
"""
import unittest
from joule.daemon import inserter
from unittest import mock
import numpy as np
import asyncio
import asynctest
from tests import helpers


class TestNilmDbInserter(unittest.TestCase):

    def setUp(self):
        self.test_path = "/test/path"
        self.my_stream = helpers.build_stream(
            name="test", datatype="uint32",
            path=self.test_path, num_elements=5)
        self.base_info = [self.test_path, "int32_3"]
        self.decim_lvl1_info = [self.test_path + "~decim-4", "float32_12"]
        self.decim_lvl2_info = [self.test_path + "~decim-16", "float32_12"]
        self.decim_lvl3_info = [self.test_path + "~decim-64", "float32_12"]

    @mock.patch("joule.daemon.daemon.nilmdb.AsyncClient", autospec=True)
    @mock.patch("joule.daemon.inserter.NilmDbDecimator", autospec=True)
    def test_processes_data_from_queue(self, mock_decimator, mock_client):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        mock_client.stream_insert = asynctest.mock.CoroutineMock()

        my_inserter = inserter.NilmDbInserter(
            mock_client, "/test-a/path-with_dashes", 100, decimate=True)
        my_decimator = mock_decimator.return_value
        my_decimator.process = asynctest.mock.CoroutineMock()
        # generate random data
        length = 100
        interval_start = 500
        step = 100
        interval_end = interval_start + (length - 1) * step
        data = helpers.create_data(self.my_stream.layout,
                                   length=length,
                                   start=interval_start,
                                   step=step)

        # insert it by block
        blk_size = 10
        queue = asyncio.Queue(loop=loop)
        for i in range(int(length / blk_size)):
            queue.put_nowait(data[i * blk_size:i * blk_size + blk_size])

        # send everything to the database
        async def stop_inserter():
            await asyncio.sleep(0.01)
            my_inserter.stop()
        tasks = [asyncio.ensure_future(stop_inserter()),
                 asyncio.ensure_future(my_inserter.process(queue, loop=loop))]
        loop.run_until_complete(asyncio.gather(*tasks))
        loop.close()
        
        # check what got inserted
        call = mock_client.stream_insert.call_args
        _, inserted_data = call[0]
        start, end = (call[1]['start'], call[1]['end'])
        np.testing.assert_array_equal(inserted_data, data)
        self.assertEqual(start, interval_start)
        self.assertEqual(end, interval_end + 1)

        # make sure the decimations were processed
        self.assertTrue(my_decimator.process.called)

    @mock.patch("joule.daemon.daemon.nilmdb.AsyncClient", autospec=True)
    def test_detects_interval_breaks(self, mock_client):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        my_inserter = inserter.NilmDbInserter(
            mock_client, "/test/path", 100, decimate=False)
        mock_client.stream_insert = asynctest.mock.CoroutineMock()

        # missing data between two inserts
        interval1_start = 500
        interval2_start = 1000
        queue = asyncio.Queue(loop=loop)
        queue.put_nowait(helpers.create_data(
            self.my_stream.layout, start=interval1_start, step=1))
        queue.put_nowait(None)  # break in the data
        queue.put_nowait(helpers.create_data(
            self.my_stream.layout, start=interval2_start, step=1))

        # send everything to the database
        async def stop_inserter():
            await asyncio.sleep(0.01)
            my_inserter.stop()

        tasks = [asyncio.ensure_future(stop_inserter()),
                 asyncio.ensure_future(my_inserter.process(queue, loop=loop))]

        loop.run_until_complete(asyncio.gather(*tasks))
        loop.close()
        # make sure two seperate intervals made it to the database
        interval1 = mock_client.stream_insert.call_args_list[0]
        start = interval1[1]['start']
        self.assertEqual(start, interval1_start)
        interval2 = mock_client.stream_insert.call_args_list[1]
        start = interval2[1]['start']
        self.assertEqual(start, interval2_start)

    @mock.patch("joule.utils.time", autospec=True)
    def test_cleans_up_streams_with_decimations(self, mock_time):
        """Inserter removes data from base and decimations based on keep_us"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        # Advance time by days after epoch
        ONE_DAY = 24*60*60*1e6  # 1 day
        KEEP_US = ONE_DAY
        times = np.arange(2, 100) * ONE_DAY
        mock_time.now = mock.Mock(side_effect=times)
        
        mock_client = mock.Mock()
        mock_client.stream_insert = asynctest.mock.CoroutineMock()
        mock_client.streams_remove = asynctest.mock.CoroutineMock()
        mock_client.stream_create = asynctest.mock.CoroutineMock()
        
        # both the base and the decimation stream already exist
        mock_info = helpers.mock_stream_info([self.base_info,
                                              self.decim_lvl1_info,
                                              self.decim_lvl2_info,
                                              self.decim_lvl3_info])

        mock_client.stream_list = asynctest.mock.CoroutineMock(
            side_effect=mock_info)

        my_inserter = inserter.NilmDbInserter(
            mock_client, self.test_path, keep_us=KEEP_US,
            decimate=True, cleanup_period=0.01)  # speed up cleanup rate
        # generate random data, data timestamps do not matter for this test
        # length of 64 creates 4 levels of decimations
        length = 64
        interval_start = 500
        step = 100
        data = helpers.create_data(self.my_stream.layout,
                                   length=length,
                                   start=interval_start,
                                   step=step)
        queue = asyncio.Queue(loop=loop)
        queue.put_nowait(data)

        # send everything to the database
        async def stop_inserter():
            # time advances by 1day=0.01s so cleanup should be called ~5 times
            await asyncio.sleep(0.05)
            my_inserter.stop()
        tasks = [asyncio.ensure_future(stop_inserter()),
                 asyncio.ensure_future(my_inserter.process(queue, loop=loop))]
        loop.run_until_complete(asyncio.gather(*tasks))

        # make sure cleanup was called on all streams
        p = self.test_path
        pd = p+"~decim-%d"
        expected_paths = [p, pd % 4, pd % 16, pd % 64, pd % 256]
        time = 1 * ONE_DAY
        for call in mock_client.streams_remove.call_args_list:
            args = call[0]
            kwargs = call[1]

            self.assertEqual(args[0], expected_paths)
            self.assertEqual(kwargs['end'], time)
            self.assertEqual(kwargs['start'], 0)
            # each cleanup call should be one more day
            time += ONE_DAY

            
class TestNilmDbDecimator(unittest.TestCase):

    def setUp(self):
        self.test_path = "/test-a/path_with-dashes"
        self.base_info = [self.test_path, "int32_4"]
        self.decim_lvl1_info = [self.test_path + "~decim-4", "float32_12"]
        self.decim_lvl2_info = [self.test_path + "~decim-16", "float32_12"]
        self.decim_lvl3_info = [self.test_path + "~decim-64", "float32_12"]

    @mock.patch("joule.daemon.daemon.nilmdb.AsyncClient", autospec=True)
    def test_finds_existing_streams(self, mock_client):
        # both the base and the decimation stream already exist
        mock_info = helpers.mock_stream_info([self.base_info,
                                              self.decim_lvl1_info])
        mock_client.stream_list = asynctest.mock.CoroutineMock(
            side_effect=mock_info)
        inserter.NilmDbDecimator(mock_client, self.test_path)
        # so the decimation stream shouldn't be created
        mock_client.stream_create.assert_not_called()

    @mock.patch("joule.daemon.daemon.nilmdb.AsyncClient", autospec=True)
    def test_creates_first_decimation_stream(self, mock_client):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        # only the base exists
        mock_info = helpers.mock_stream_info([self.base_info])
        mock_client.stream_list = asynctest.mock.CoroutineMock(
            side_effect=mock_info)
        mock_client.stream_create = asynctest.mock.CoroutineMock()
        mock_client.stream_insert = asynctest.mock.CoroutineMock()
        my_decimator = inserter.NilmDbDecimator(mock_client, self.test_path)
        # initialization is lazy so we have to process some data
        data = helpers.create_data("int32_4", length=1)
        loop.run_until_complete(my_decimator.process(data))
        loop.close()
        # so the decimation stream should be created
        mock_client.stream_create.assert_called_with(*self.decim_lvl1_info)

    @mock.patch("joule.daemon.daemon.nilmdb.AsyncClient", autospec=True)
    def test_creates_subsequent_decimation_streams(self, mock_client):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        # both the base and the decimation stream already exist
        mock_info = helpers.mock_stream_info([self.base_info,
                                              self.decim_lvl1_info])
        mock_client.stream_list = asynctest.mock.CoroutineMock(
            side_effect=mock_info)
        mock_client.stream_create = asynctest.mock.CoroutineMock()
        mock_client.stream_insert = asynctest.mock.CoroutineMock()

        my_decimator = inserter.NilmDbDecimator(
            mock_client, self.decim_lvl1_info[0])
        # initialization is lazy so we have to process some data
        data = helpers.create_data("int32_4", length=1)
        loop.run_until_complete(my_decimator.process(data))
        # the 2nd level decimation should be created
        mock_client.stream_create.assert_called_with(*self.decim_lvl2_info)
        loop.close()
        
    @mock.patch("joule.daemon.daemon.nilmdb.AsyncClient", autospec=True)
    def test_correctly_decimates_data(self, mock_client):

        data = helpers.create_data("int32_4", length=16)
        ts = data['timestamp']
        vals = data['data']

        mock_info = helpers.mock_stream_info([self.base_info,
                                              self.decim_lvl1_info,
                                              self.decim_lvl2_info,
                                              self.decim_lvl3_info])
        mock_client.stream_list = asynctest.mock.CoroutineMock(
            side_effect=mock_info)
        mock_client.stream_insert = asynctest.mock.CoroutineMock()

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        async def run():
            my_decimator = inserter.NilmDbDecimator(
                mock_client, self.base_info[0])
            # insert data in chunks to test decimation buffer
            await my_decimator.process(data[:7])
            await my_decimator.process(data[7:])

        loop.run_until_complete(run())
        loop.close()
        
        inserted_lvl2 = False
        for args in mock_client.stream_insert.call_args_list:
            (path, data) = args[0]
            r_vals = data['data']
            r_ts = data['timestamp']
            kwargs = args[1]
            if(path == self.decim_lvl2_info[0]):
                """ upper decimations match incoming data bounds
                **note actual bounds here** the start/end match the
                data points *given* to this decimation level here we
                are looking at x16 so the timestamps are from the x4 stream
                so start is the mean of the first 4  timestamps, and end is
                likewise"""
                self.assertEqual(kwargs['start'], np.mean(ts[:4]))
                self.assertEqual(kwargs['end'], np.mean(ts[-4:]) + 1)
                # check the contents of the data array
                np.testing.assert_array_almost_equal(r_ts, np.mean(ts))
                # data mean,min,max
                expected_vals = np.hstack((np.mean(vals, axis=0),
                                           np.min(vals, axis=0),
                                           np.max(vals, axis=0)))
                np.testing.assert_array_almost_equal(
                    np.squeeze(r_vals), expected_vals)
                inserted_lvl2 = True
        # make sure level2 (x16) decimation was performed
        self.assertTrue(inserted_lvl2)

    def test_finalize_inserts_interval_break(self):
        pass
