import asynctest
from joule import api, utilities, models
import numpy as np
import asyncio


class TestDataMethods(asynctest.TestCase):

    async def setUp(self):
        self.node = api.Node()

    async def tearDown(self):
        await self.node.close()

    async def test_data_read(self):
        stream = await self.node.data_read("/live/base", end=utilities.time_now())
        num_intervals = 0
        # data should start at 0 and count up by 10's every interval
        while True:
            try:
                data = await stream.read()
                # check the data
                expected = np.arange(0, len(data) * 10, 10)
                np.testing.assert_array_equal(data['data'], expected)
                if stream.end_of_interval:
                    num_intervals += 1
                stream.consume(len(data))
            except models.pipes.EmptyPipe:
                break
        await stream.close()

    async def test_data_read_max_rows(self):
        pass

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
            np.diff(data['data']))

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
        while True:
            try:
                data = await pipe.read()
                nrows += len(data)
                pipe.consume(len(data))
            except models.pipes.EmptyPipe:
                break
        self.assertEqual(blk_size*nblks, nrows)

    async def test_data_delete(self):
        pass
