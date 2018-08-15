from tests import helpers
import time
import threading
import numpy as np
import asyncio

from joule.models.pipes import LocalPipe, PipeError, EmptyPipe


class TestLocalPipe(helpers.AsyncTestCase):

    def test_pipes_numpy_arrays(self):
        """writes to pipe sends data to reader and any subscribers"""
        LAYOUT = "int8_2"
        LENGTH = 1003
        loop = asyncio.get_event_loop()
        my_pipe = LocalPipe(LAYOUT, loop, name="pipe")
        # test timeouts, since the writer is slow
        my_pipe.TIMEOUT_INTERVAL = 0.05
        subscriber_pipe = LocalPipe(LAYOUT, loop)
        subscriber_pipe2 = LocalPipe(LAYOUT, loop)
        my_pipe.subscribe(subscriber_pipe)
        my_pipe.subscribe(subscriber_pipe2)
        test_data = helpers.create_data(LAYOUT, length=LENGTH)

        #    print(test_data['data'][:,1])

        async def writer():
            for block in helpers.to_chunks(test_data, 270):
                await asyncio.sleep(0.1)
                await my_pipe.write(block)

        async def reader():
            blk_size = 357
            data_cursor = 0  # index into test_data
            while data_cursor != len(test_data):
                # consume all data in pipe
                data = await my_pipe.read()
                rows_used = min(len(data), blk_size)
                used_data = data[:rows_used]
                # print(used_data['data'][:,1])
                my_pipe.consume(rows_used)
                start_pos = data_cursor
                end_pos = data_cursor + len(used_data)
                np.testing.assert_array_equal(used_data,
                                              test_data[start_pos:end_pos])
                data_cursor += len(used_data)

        async def subscriber():
            blk_size = 493
            data_cursor = 0  # index into test_data
            while data_cursor != len(test_data):
                # consume all data in pipe
                data = await subscriber_pipe.read()
                rows_used = min(len(data), blk_size)
                used_data = data[:rows_used]
                # print(used_data['data'][:,1])
                subscriber_pipe.consume(rows_used)
                start_pos = data_cursor
                end_pos = data_cursor + len(used_data)
                np.testing.assert_array_equal(used_data,
                                              test_data[start_pos:end_pos])
                data_cursor += len(used_data)

        loop = asyncio.get_event_loop()
        tasks = [asyncio.ensure_future(writer()),
                 asyncio.ensure_future(reader()),
                 asyncio.ensure_future(subscriber())]

        loop.run_until_complete(asyncio.gather(*tasks))

        data = subscriber_pipe2.read_nowait()
        np.testing.assert_array_equal(test_data, data)

    def test_read_data_must_be_consumed(self):
        """writes to pipe sends data to reader and any subscribers"""
        LAYOUT = "float32_2"
        LENGTH = 500
        UNCONSUMED_ROWS = 4
        # test that the default event loop is used if loop is not specified
        my_pipe = LocalPipe(LAYOUT, None)
        test_data = helpers.create_data(LAYOUT, length=LENGTH)
        #    print(test_data['data'][:,1])
        my_pipe.write_nowait(test_data)

        async def reader():
            data = await my_pipe.read()
            my_pipe.consume(0)
            # should get the same data back
            repeat = await my_pipe.read()
            np.testing.assert_array_equal(data, repeat)
            my_pipe.consume(len(data) - UNCONSUMED_ROWS)
            next_data = await my_pipe.read()
            np.testing.assert_array_equal(data[-UNCONSUMED_ROWS:],
                                          next_data[:UNCONSUMED_ROWS + 1])

        loop = asyncio.get_event_loop()
        loop.run_until_complete(reader())

    def test_nowait_read_writes(self):
        LAYOUT = "int8_2"
        LENGTH = 500
        loop = asyncio.get_event_loop()
        my_pipe = LocalPipe(LAYOUT, loop)
        my_subscriber = LocalPipe(LAYOUT, loop)
        my_pipe.subscribe(my_subscriber)
        test_data = helpers.create_data(LAYOUT, length=LENGTH)
        my_pipe.write_nowait(test_data)
        result = my_pipe.read_nowait()
        # read data should match written data
        np.testing.assert_array_almost_equal(test_data['data'], result['data'])
        np.testing.assert_array_almost_equal(
            test_data['timestamp'], result['timestamp'])
        # subscriber should have a copy too
        result = my_subscriber.read_nowait()
        np.testing.assert_array_almost_equal(test_data['data'], result['data'])
        np.testing.assert_array_almost_equal(
            test_data['timestamp'], result['timestamp'])

    def test_invalid_write_nowait_inputs(self):
        LAYOUT = "int8_2"
        loop = asyncio.get_event_loop()
        my_pipe = LocalPipe(LAYOUT, loop, name="testpipe")
        with self.assertLogs(level="INFO"):
            my_pipe.write_nowait(np.array([[]]))
        with self.assertRaises(PipeError):
            my_pipe.write_nowait([1, 2, 3])

    def test_different_format_writes(self):
        LAYOUT = "int8_2"
        loop = asyncio.get_event_loop()
        my_pipe = LocalPipe(LAYOUT, loop, name="testpipe")

        test_data = helpers.create_data(LAYOUT, length=4, step=1, start=106)

        async def write():
            # write unstructured numpy arrays
            await my_pipe.write(np.array([[1, 1, 1]]))
            await my_pipe.write(np.array([[2, 2, 2],
                                          [3, 3, 3]]))

            # logs empty writes
            with self.assertLogs(level="INFO") as logs:
                await my_pipe.write(np.array([[]]))

            # errors on invalid write types
            bad_data = [[100, 1, 2], 'invalid', 4, None, np.array([4, 8])]
            for data in bad_data:
                with self.assertRaises(PipeError):
                    await my_pipe.write(data)

            # write structured numpy arrays
            await my_pipe.write(test_data)

        loop = asyncio.get_event_loop()
        loop.run_until_complete(write())
        result = my_pipe.read_nowait(flatten=True)
        np.testing.assert_array_equal(result[:3], [[1, 1, 1],
                                                   [2, 2, 2],
                                                   [3, 3, 3]])
        my_pipe.consume(3)
        result = my_pipe.read_nowait()
        np.testing.assert_array_equal(result, test_data)

    def test_caching(self):
        LAYOUT = "float32_2"
        LENGTH = 128
        CACHE_SIZE = 40
        # test that the default event loop is used if loop is not specified
        my_pipe = LocalPipe(LAYOUT, None)
        my_pipe.enable_cache(CACHE_SIZE)
        test_data = helpers.create_data(LAYOUT, length=LENGTH, start=1, step=1)

        async def writer():
            for block in helpers.to_chunks(test_data, 4):
                await asyncio.sleep(.1)
                await my_pipe.write(block)
            await my_pipe.flush_cache()

        num_reads = 0

        async def reader():
            nonlocal num_reads
            index = 0
            while True:
                data = await my_pipe.read()
                my_pipe.consume(len(data))
                # make sure the data is correct
                np.testing.assert_array_equal(test_data[index:index + len(data)],
                                              data)
                num_reads += 1
                index += len(data)

                if index == len(test_data):
                    break

        loop = asyncio.get_event_loop()
        loop.run_until_complete(asyncio.gather(reader(), writer()))
        self.assertLessEqual(num_reads, np.ceil(LENGTH / CACHE_SIZE))

    def test_nowait_read_empties_queue(self):
        LAYOUT = "int8_2"
        LENGTH = 50
        loop = asyncio.get_event_loop()
        my_pipe = LocalPipe(LAYOUT, loop)
        test_data = helpers.create_data(LAYOUT, length=LENGTH)

        async def writer():
            for row in test_data:
                await my_pipe.write(np.array([row]))

        loop = asyncio.get_event_loop()
        loop.run_until_complete(writer())

        result = my_pipe.read_nowait()

        np.testing.assert_array_almost_equal(test_data['data'], result['data'])
        np.testing.assert_array_almost_equal(
            test_data['timestamp'], result['timestamp'])

    def test_nowait_read_does_not_block(self):
        LAYOUT = "int8_2"
        LENGTH = 50
        loop = asyncio.get_event_loop()
        my_pipe = LocalPipe(LAYOUT, loop)
        test_data = helpers.create_data(LAYOUT, length=LENGTH)
        my_pipe.write_nowait(test_data)
        self.assertEqual(len(my_pipe.read_nowait()), LENGTH)
        # another read executes immediately because there is unconsumed data
        self.assertEqual(len(my_pipe.read_nowait()), LENGTH)
        # now consume the data and the next call to read execute immediately
        # even though there is no data to be returned
        my_pipe.consume(LENGTH)
        self.assertEqual(0, len(my_pipe.read_nowait(flatten=True)))
        return

    def test_handles_flat_and_structured_arrays(self):
        """converts flat arrays to structured arrays and returns
           either flat or structured arrays depending on [flatten] parameter"""
        LAYOUT = "float64_1"
        LENGTH = 1000
        my_pipe = LocalPipe(LAYOUT, loop=asyncio.get_event_loop())
        test_data = helpers.create_data(LAYOUT, length=LENGTH)
        flat_data = np.c_[test_data['timestamp'][:, None], test_data['data']]

        async def reader():
            sdata = await my_pipe.read()
            fdata = await my_pipe.read(flatten=True)
            np.testing.assert_array_almost_equal(
                sdata['timestamp'], test_data['timestamp'])
            np.testing.assert_array_almost_equal(
                sdata['data'], test_data['data'])
            np.testing.assert_array_almost_equal(fdata, flat_data)
            np.testing.assert_array_almost_equal(fdata, flat_data)

        loop = asyncio.get_event_loop()
        tasks = [asyncio.ensure_future(my_pipe.write(flat_data)),
                 asyncio.ensure_future(reader())]
        loop.run_until_complete(asyncio.gather(*tasks))

    def test_raises_consume_errors(self):
        LAYOUT = "int32_3"
        LENGTH = 1000
        my_pipe = LocalPipe(LAYOUT, loop=asyncio.get_event_loop())
        test_data = helpers.create_data(LAYOUT, length=LENGTH)
        my_pipe.write_nowait(test_data)
        read_data = my_pipe.read_nowait()
        # can't consume more than was read
        with self.assertRaises(PipeError) as e:
            my_pipe.consume(len(read_data) + 1)
        self.assertTrue('consume' in str(e.exception))
        # can't consume less than zero
        with self.assertRaises(PipeError) as e:
            my_pipe.consume(-1)
        self.assertTrue('negative' in str(e.exception))

    def test_handles_interval_breaks(self):
        LAYOUT = "int32_3"
        LENGTH = 1000
        my_pipe = LocalPipe(LAYOUT, loop=asyncio.get_event_loop(), name="pipe")
        test_data1 = helpers.create_data(LAYOUT, length=LENGTH)
        test_data2 = helpers.create_data(LAYOUT, length=LENGTH)
        my_pipe.write_nowait(test_data1)
        my_pipe.close_interval_nowait()
        my_pipe.write_nowait(test_data2)

        async def reader():
            # read the first interval
            read_data = await my_pipe.read()
            self.assertTrue(my_pipe.end_of_interval)
            my_pipe.consume(len(read_data) - 20)
            np.testing.assert_array_equal(test_data1, read_data)

            # read the second interval
            read_data = await my_pipe.read()
            self.assertFalse(my_pipe.end_of_interval)
            self.assertEqual(len(read_data), len(test_data2) + 20)
            my_pipe.consume(len(read_data))
            np.testing.assert_array_equal(test_data2, read_data[20:])

        loop = asyncio.get_event_loop()
        loop.run_until_complete(reader())