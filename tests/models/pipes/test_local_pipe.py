from tests import helpers
from unittest import mock
import numpy as np
import asyncio
from icecream import ic
from joule.models.pipes import LocalPipe, PipeError, OutputPipe
from joule.errors import EmptyPipeError


class TestLocalPipe(helpers.AsyncTestCase):

    def test_pipes_numpy_arrays(self):
        """writes to pipe sends data to reader and any subscribers"""
        LAYOUT = "int8_2"
        LENGTH = 1003
        ''
        my_pipe = LocalPipe(LAYOUT, name="pipe")
        # test timeouts, since the writer is slow
        my_pipe.TIMEOUT_INTERVAL = 0.05
        subscriber_pipe = LocalPipe(LAYOUT)
        subscriber_pipe2 = LocalPipe(LAYOUT)
        my_pipe.subscribe(subscriber_pipe)
        my_pipe.subscribe(subscriber_pipe2)
        test_data = helpers.create_data(LAYOUT, length=LENGTH)
        reader_rx_data = np.empty(test_data.shape, test_data.dtype)
        subscriber_rx_data = np.empty(test_data.shape, test_data.dtype)

        #    print(test_data['data'][:,1])

        async def writer():
            for block in helpers.to_chunks(test_data, 270):
                await asyncio.sleep(0.1)
                await my_pipe.write(block)
            await my_pipe.close()

        async def reader():
            # note this is kind of delicate, you can only read data twice
            # if the pipe is closed so it might look like you didn't finish all
            # the data if the last read ignores data past blk_size
            blk_size = 600
            rx_idx = 0
            while not my_pipe.is_empty():
                # consume data in pipe
                data_chunk = await my_pipe.read()
                rows_used = min(len(data_chunk), blk_size)
                reader_rx_data[rx_idx:rx_idx + rows_used] = data_chunk[:rows_used]
                rx_idx += rows_used
                my_pipe.consume(rows_used)

        async def subscriber():
            rx_idx = 0
            while not subscriber_pipe.is_empty():
                # consume data in pipe
                try:
                    data_chunk = await subscriber_pipe.read()
                except EmptyPipeError:
                    # can happen if the writer is finished but hasn't
                    # closed the pipe before the subscriber calls read()
                    break
                subscriber_rx_data[rx_idx:rx_idx + len(data_chunk)] = data_chunk
                rx_idx += len(data_chunk)
                subscriber_pipe.consume(len(data_chunk))

        async def runner():
            #await writer()
            #await reader()
            #await subscriber()
            await asyncio.gather(writer(),
                                 reader(),
                                 subscriber())
        asyncio.run(runner())

        data = subscriber_pipe2.read_nowait()
        np.testing.assert_array_equal(test_data, data)
        np.testing.assert_array_equal(test_data, reader_rx_data)
        np.testing.assert_array_equal(test_data, subscriber_rx_data)

    def test_read_data_must_be_consumed(self):
        # writes to pipe sends data to reader and any subscribers
        LAYOUT = "float32_2"
        LENGTH = 500
        UNCONSUMED_ROWS = 4
        my_pipe = LocalPipe(LAYOUT)
        chunk1 = helpers.create_data(LAYOUT, length=LENGTH)
        chunk2 = helpers.create_data(LAYOUT, length=LENGTH)
        chunk3 = helpers.create_data(LAYOUT, length=LENGTH)

        my_pipe.write_nowait(chunk1)

        async def reader():
            await my_pipe.read()
            my_pipe.consume(0)
            # should get the same data back on the next read
            # add a second copy of the test data
            await my_pipe.write(chunk2)
            rx_data = await my_pipe.read()
            # two copies of the data now
            np.testing.assert_array_equal(chunk1, rx_data[:len(chunk1)])
            np.testing.assert_array_equal(chunk2, rx_data[len(chunk1):])
            # write another copy but consume the first
            my_pipe.consume(len(chunk1))
            await my_pipe.write(chunk3)
            rx_data = await my_pipe.read()
            # two copies of the data now
            np.testing.assert_array_equal(chunk2, rx_data[:len(chunk2)])
            np.testing.assert_array_equal(chunk3, rx_data[len(chunk2):])
            my_pipe.consume(len(chunk2))
            await my_pipe.close()
            # now a read should return immediately with the unconsumed data
            rx_data = await my_pipe.read()
            np.testing.assert_array_equal(chunk3, rx_data)
            # the pipe should be empty but still return the old data
            rx_data = await my_pipe.read()
            np.testing.assert_array_equal(chunk3, rx_data)
            # only after consuming the remaining data does it raise an exception
            my_pipe.consume(len(rx_data))
            # another read should cause an exception (even if the data hasn't been consumed)
            with self.assertRaises(EmptyPipeError):
                await my_pipe.read()
            # the pipe should be empty
            self.assertTrue(my_pipe.is_empty())

        asyncio.run(reader())

    def test_consumes_data(self):
        LAYOUT = "int8_2"
        LENGTH = 500
        test_data = helpers.create_data(LAYOUT, length=LENGTH)
        my_pipe = LocalPipe("int8_2")
        my_pipe.write_nowait(test_data)
        my_pipe.close_nowait()
        async def reader():
            data = await my_pipe.read()
            assert len(data) == LENGTH
            my_pipe.consume(100)
            data = await my_pipe.read()
            assert len(data) == LENGTH - 100
            my_pipe.consume_all()
            assert my_pipe.is_empty()

        asyncio.run(reader())

    def test_nowait_read_writes(self):
        LAYOUT = "int8_2"
        LENGTH = 500
        ''
        my_pipe = LocalPipe(LAYOUT)
        my_subscriber = LocalPipe(LAYOUT)
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
        ''
        my_pipe = LocalPipe(LAYOUT, name="testpipe")
        with self.assertLogs(level="INFO"):
            my_pipe.write_nowait(np.array([[]]))
        with self.assertRaises(PipeError):
            my_pipe.write_nowait([1, 2, 3])

    def test_different_format_writes(self):
        LAYOUT = "int8_2"
        ''
        my_pipe = LocalPipe(LAYOUT, name="testpipe")

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

        ''
        asyncio.run(write())
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
        my_pipe = LocalPipe(LAYOUT)
        my_pipe.enable_cache(CACHE_SIZE)
        test_data = helpers.create_data(LAYOUT, length=LENGTH, start=1, step=1)

        async def writer():
            for block in helpers.to_chunks(test_data, 4):
                await asyncio.sleep(.1)
                await my_pipe.write(block)
            # closing the interval should flush the data
            await my_pipe.close_interval()
            # add a dummy section after the interval break
            await my_pipe.write(np.ones((35, 3)))
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
            # now get the dummy section after the interval break
            data = await my_pipe.read(flatten=True)
            np.testing.assert_array_equal(data, np.ones((35, 3)))

        async def runner():
            await asyncio.gather(reader(), writer())
        asyncio.run(runner())
        self.assertLessEqual(num_reads, np.ceil(LENGTH / CACHE_SIZE))

    def test_nowait_read_empties_queue(self):
        LAYOUT = "int8_2"
        LENGTH = 50
        my_pipe = LocalPipe(LAYOUT)
        test_data = helpers.create_data(LAYOUT, length=LENGTH)

        async def writer():
            for row in test_data:
                await my_pipe.write(np.array([row]))

        ''
        asyncio.run(writer())

        result = my_pipe.read_nowait()

        np.testing.assert_array_almost_equal(test_data['data'], result['data'])
        np.testing.assert_array_almost_equal(
            test_data['timestamp'], result['timestamp'])

    def test_nowait_read_does_not_block(self):
        LAYOUT = "int8_2"
        LENGTH = 50
        my_pipe = LocalPipe(LAYOUT)
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
        # converts flat arrays to structured arrays and returns
        #   either flat or structured arrays depending on [flatten] parameter
        LAYOUT = "float64_1"
        LENGTH = 1000
        my_pipe = LocalPipe(LAYOUT)
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

        asyncio.run(my_pipe.write(flat_data))
        asyncio.run(my_pipe.close())
        asyncio.run(reader())

    def test_raises_consume_errors(self):
        LAYOUT = "int32_3"
        LENGTH = 1000
        my_pipe = LocalPipe(LAYOUT)
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
        my_pipe = LocalPipe(LAYOUT, name="pipe")
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

        asyncio.run(reader())

    def test_nowait_function_exceptions(self):
        pipe = LocalPipe(layout="float32_3")
        subscriber = LocalPipe(layout="float32_3", close_cb=mock.Mock())
        fd_subscriber = OutputPipe()
        # cannot close_nowait if there is a callback
        with self.assertRaises(PipeError):
            subscriber.close_nowait()

        # can write_nowait if only localpipe subscribers
        pipe.subscribe(subscriber)
        pipe.write_nowait(np.ones((100, 4)))
        # cannot if any subscribers are not localpipes
        pipe.subscribe(fd_subscriber)
        with self.assertRaises(PipeError):
            pipe.write_nowait(np.ones((100, 4)))

        # cannot close_nowait if there are subscribers
        pipe.subscribe(subscriber)
        with self.assertRaises(PipeError):
            pipe.close_nowait()
