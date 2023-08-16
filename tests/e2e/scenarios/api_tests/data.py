import unittest

import joule.errors
from joule import api, utilities, models
import numpy as np
import asyncio
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
        while True:
            try:
                data = await stream.read()
                # check the data
                expected = np.arange(0, len(data) * 10, 10)
                np.testing.assert_array_equal(data['data'], expected[:, None])
                if stream.end_of_interval:
                    num_intervals += 1
                stream.consume(len(data))
            except models.pipes.EmptyPipe:
                break
        await stream.close()

    async def test_data_read_max_rows(self):
        stream = await self.node.data_read("/live/base", max_rows=100)
        total_rows = 0
        while True:
            try:
                data = await stream.read()
                total_rows += len(data)
                stream.consume(len(data))
            except models.pipes.EmptyPipe:
                break
        self.assertLessEqual(total_rows, 100)

    async def test_data_subscribe(self):
        stream = await self.node.data_subscribe("/live/plus1")
        num_reads = 0
        TARGET_READS = 3
        MIN_DATA = 20
        # data should start at 0 and count up by 10's every interval
        while True:
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
        await self.node.data_delete("/archive/data1")
        pipe = await self.node.data_write("/archive/data1")
        blk_size = 100
        nblks = 1000
        time = utilities.time_now()
        for i in range(nblks):
            ts = np.linspace(time, time + blk_size, blk_size)
            self.assertEqual(min(np.diff(ts)), 1)
            data1 = np.random.random((blk_size, 1))
            data2 = np.random.random((blk_size, 1))

            res = np.hstack((ts[:, None], data1, data2))
            time = time + blk_size + 1
            await pipe.write(res)
        await pipe.close()
        # now read the data back
        pipe = await self.node.data_read("/archive/data1", start=0)
        nrows = 0
        while not pipe.is_empty():
            data = await pipe.read()
            nrows += len(data)
            pipe.consume(len(data))

        self.assertEqual(blk_size * nblks, nrows)

    @unittest.skip("TODO: something with postgres auth doesn't work on docker")
    async def test_db_data_access(self):
        # should be able to read data streams from postgres
        await self.node.data_delete("/archive/data1")
        stream = await self.node.data_stream_get("/archive/data1")
        blk_size = 100
        time = utilities.time_now()
        ts = np.linspace(time, time + blk_size, blk_size)
        self.assertEqual(min(np.diff(ts)), 1)
        data1 = np.random.random((blk_size, 1))
        data2 = np.random.random((blk_size, 1))
        res = np.hstack((ts[:, None], data1, data2))
        pipe = await self.node.data_write(stream)
        await pipe.write(res)
        await pipe.close()
        stream_id = stream.id
        engine = await self.node.db_connect()
        with engine.connect() as conn:
            resp = conn.execute(text(f"SELECT count(*) from data.stream{stream_id}"))
            row_count = resp.fetchone()[0]
            print(f"resp is {row_count}")
            assert row_count == blk_size

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
            assert "monotonic" in str(e)
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
            assert "already exists" in str(e)
            pass
        # write data with NaN's
        await self.node.data_delete("/archive/data1")
        pipe = await self.node.data_write("/archive/data1")
        res[0, 2] = np.nan
        try:
            await pipe.write(res)
            await pipe.close()
            self.fail("should have raised an exception")
        except joule.errors.ApiError as e:
            assert "NaN" in str(e)
            pass

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
        while not data_in.is_empty():
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
