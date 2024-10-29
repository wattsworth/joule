import unittest
import traceback
import joule.errors
from joule import api, utilities, models
import numpy as np
import asyncio
import sys
from sqlalchemy import text


class TestDataMethods(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self):
        self.node = api.get_node()

    async def asyncTearDown(self):
        await self.node.close()

    async def test_data_read(self):
        stream = await self.node.data_read("/live/base")
        num_intervals = 0
        # data should start at 0 and count up by 10's every interval
        while await stream.not_empty():
            data = await stream.read()
            # check the data
            expected = np.arange(0, len(data) * 10, 10)
            np.testing.assert_array_equal(data['data'], expected[:, None])
            if stream.end_of_interval:
                num_intervals += 1
            stream.consume(len(data))
        await stream.close()

    async def test_data_read_max_rows(self):
        stream = await self.node.data_read("/live/base", max_rows=100)
        total_rows = 0
        while await stream.not_empty():
            data = await stream.read()
            total_rows += len(data)
            stream.consume(len(data))
        self.assertLessEqual(total_rows, 105) # max rows is approximate, see joule/sql/row_count.sql

    async def test_data_subscribe(self):
        stream = await self.node.data_subscribe("/live/plus1")
        num_reads = 0
        TARGET_READS = 3
        MIN_DATA = 20
        # data should start at 0 and count up by 10's every interval
        while await stream.not_empty():
            data = await stream.read()
            await asyncio.sleep(0.5)
            num_reads += 1
            if num_reads >= TARGET_READS and len(data) > MIN_DATA:
                break
        stream.consume(len(data))
        np.testing.assert_array_almost_equal(
            np.ones((len(data) - 1)) * 10,
            np.diff(data['data'], axis=0).squeeze())

        await stream.close()

    async def test_data_write(self):
        time = utilities.time_now()
        print("deleting data...", end="")
        await self.node.data_delete("/archive/data1")
        print(f"OK {(utilities.time_now()-time)/1000:.2f}s")

        print("writing data...", end="")
        pipe = await self.node.data_write("/archive/data1")
        blk_size = 100
        nblks = 10
        _time = utilities.time_now()
        sys.stdout.flush()
        start_time = utilities.time_now()
        ts = np.linspace(start_time, start_time+ nblks*blk_size*100, nblks*blk_size, dtype=int)
        # make sure all timestamps are unique
        self.assertGreaterEqual(min(np.diff(ts)), 99)
        for i in range(nblks):
            # ts is a monotonic increasing sequence of timestamps counting by 100's
            ts_chunk = ts[i*blk_size:(i+1)*blk_size]
            self.assertEqual(len(ts_chunk), blk_size)
            data1 = np.random.random((blk_size, 1))
            data2 = np.random.random((blk_size, 1))
            res = np.hstack((ts_chunk[:, None], data1, data2))
            time = time + blk_size + 1
            await pipe.write(res)
        await pipe.close()
        print(f"OK {(utilities.time_now()-_time)/1000:.2f}s")

        print("reading data...", end="")
        time = utilities.time_now()
        # now read the data back
        pipe = await self.node.data_read("/archive/data1", start=0)
        nrows = 0
        while await pipe.not_empty():
            data = await pipe.read()
            nrows += len(data)
            pipe.consume(len(data))
        self.assertEqual(blk_size * nblks, nrows)
        print(f"OK {(utilities.time_now()-time)/1000:.2f}s")

    async def test_data_merges_successive_writes(self):
        await self.node.data_delete("/archive/data1")
        n = utilities.time_now()
        blk_size = 5
        ts = np.linspace(n+10e6, n+15e6, blk_size)
        data = np.random.random((blk_size, 2))
        pipe = await self.node.data_write("/archive/data1")
        #print([int(x) for x in ts])
        await pipe.write(np.hstack((ts[:, None], data)))
        await pipe.close()

        # now write some data that will *not* merge into the previous data interval
        ts = np.linspace(n+16e6, n+20e6, blk_size)
        pipe = await self.node.data_write("/archive/data1", merge_gap=1e3)
        #print([int(x) for x in ts])
        await pipe.write(np.hstack((ts[:, None], data)))
        await pipe.close()

        # now write some data that will merge into the previous data interval
        ts = np.linspace(n+21e6, n+25e6, blk_size)
        #print([int(x) for x in ts])
        pipe = await self.node.data_write("/archive/data1", merge_gap=2e6)
        await pipe.write(np.hstack((ts[:, None], data)))
        await pipe.close()

        # expect 2 intervals
        intervals = await self.node.data_intervals("/archive/data1")
        #print(intervals)
        self.assertEqual(len(intervals), 2)

        # now read the data back
        pipe = await self.node.data_read("/archive/data1", start=0)
        nrows = 0
        first_block = True
        #print("===== READING DATA ======")
        while await pipe.not_empty():
            data = await pipe.read()
            #print([int(x) for x in data['timestamp']])
            nrows += len(data)
            #if pipe.end_of_interval:
            #    print("--- interval break ---")
            if pipe.end_of_interval and first_block:
                # 1st block has one chunk of data
                self.assertEqual(len(data), blk_size)
                first_block = False
                nrows=0
            pipe.consume(len(data))
        # 2nd block has two chunks of data
        self.assertFalse(first_block) # make sure we already read the first block
        self.assertEqual(nrows, blk_size*2)

    async def test_data_write_invalid_values(self):
        # write duplicate data to a pipe
        await self.node.data_delete("/archive/data1")
        pipe = await self.node.data_write("/archive/data1")
        blk_size = 100
        time = utilities.time_now()
        ts = np.linspace(time, time + blk_size, blk_size)
        self.assertEqual(min(np.diff(ts)), 1)
        data1 = np.random.random((blk_size, 1))
        data2 = np.random.random((blk_size, 1))
        res = np.hstack((ts[:, None], data1, data2))
        await pipe.write(res[75:, :])
        try:
            await pipe.write(res[:50, :])
            await pipe.close()

            self.fail("should have raised an exception")
        except joule.errors.ApiError as e:
            assert "monotonic" in traceback.format_exc()
            pass
        # write duplicate data across two pipes
        await self.node.data_delete("/archive/data1")
        pipe = await self.node.data_write("/archive/data1")
        await pipe.write(res[25:, :])
        await pipe.close()
        pipe = await self.node.data_write("/archive/data1")
        try:
            await pipe.write(res[:50, :])
            await pipe.close()
            self.fail("should have raised an exception")
        except joule.errors.ApiError as e:
            assert "already exists" in traceback.format_exc()
        # write data with NaN's
        await self.node.data_delete("/archive/data1")
        pipe = await self.node.data_write("/archive/data1")
        res[0, 2] = np.nan
        try:
            await pipe.write(res)
            await pipe.close()
            self.fail("should have raised an exception")
        except joule.errors.ApiError as e:
            assert "NaN" in traceback.format_exc()

    async def test_data_delete(self):
        # copy data to a new stream
        src = await self.node.data_stream_get("/live/base")
        # wait for source stream to have data in it
        while True:
            src_info = await self.node.data_stream_info(src)
            if src_info.rows > 10:
                break
            await asyncio.sleep(1)  # 10Hz rate so this should just happen once
        dest = await self.node.data_stream_create(src, "/tmp")
        data_in = await self.node.data_read(src)
        data_out = await self.node.data_write(dest)
        first_ts = None
        last_ts = None
        while await data_in.not_empty():
            data = await data_in.read()
            if first_ts is None:
                first_ts = data['timestamp'][0]
            last_ts = data['timestamp'][-1]
            data_in.consume(len(data))
            await data_out.write(data)

        await data_out.close()
        dest_info = await self.node.data_stream_info(dest)
        self.assertGreater(dest_info.rows, 2)
        # remove all but the first and last samples
        await self.node.data_delete(dest, start=first_ts + 1, end=last_ts - 1)
        dest_info = await self.node.data_stream_info(dest)
        self.assertEqual(dest_info.rows, 2)
        await self.node.data_stream_delete(dest)
