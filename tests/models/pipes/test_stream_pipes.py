from joule.models.pipes import InputPipe, OutputPipe, PipeError, LocalPipe
from joule.models.pipes.factories import reader_factory, writer_factory

import os
import numpy as np
import asyncio
import unittest.mock
from tests import helpers

"""
Tests NumpyPipes with subprocess pipes 
"""


class TestStreamingPipes(helpers.AsyncTestCase):

    def test_pipes_numpy_arrays(self):
        LAYOUT = "int8_2"
        LENGTH = 1000
        (fd_r, fd_w) = os.pipe()
        ''
        npipe_in = InputPipe(layout=LAYOUT, reader_factory=reader_factory(fd_r))
        npipe_out = OutputPipe(layout=LAYOUT, writer_factory=writer_factory(fd_w))
        test_data = helpers.create_data(LAYOUT, length=LENGTH)

        async def writer():
            for block in helpers.to_chunks(test_data, 270):
                await npipe_out.write(block)
                await asyncio.sleep(0.01)

        async def reader():
            blk_size = 357
            data_cursor = 0  # index into test_data
            run_count = 0
            while data_cursor != len(test_data):
                # consume all data in pipe
                data = await npipe_in.read()
                rows_used = min(len(data), blk_size)
                used_data = data[:rows_used]
                # print(used_data['data'][:,1])
                npipe_in.consume(rows_used)
                start_pos = data_cursor
                end_pos = data_cursor + len(used_data)
                np.testing.assert_array_equal(used_data,
                                              test_data[start_pos:end_pos])

                data_cursor += len(used_data)
                run_count += 1

            # make sure the reads are broken up (otherwise test is lame...)
            self.assertGreater(run_count, 2)

        async def runner():
            await asyncio.gather(writer(),reader())
            await npipe_in.close()
            await npipe_out.close()

        asyncio.run(runner())

    def test_reconstructs_fragmented_data(self):
        LAYOUT = "int8_2"
        LENGTH = 1000
        (fd_r, fd_w) = os.pipe()
        ''
        # wrap the file descriptors in numpypipes
        npipe_in = InputPipe(layout=LAYOUT, reader_factory=reader_factory(fd_r))
        test_data = helpers.create_data(LAYOUT, length=LENGTH)

        async def writer():
            b_data = test_data.tobytes()
            f = open(fd_w, 'wb', 0)
            f.write(b_data[:395])
            await asyncio.sleep(0.05)
            f.write(b_data[395:713])
            await asyncio.sleep(0.05)
            f.write(b_data[713:])
            f.close()

        async def reader():
            data_cursor = 0  # index into test_data
            run_count = 0
            while data_cursor != len(test_data):
                # consume all data in pipe
                data = await npipe_in.read()
                npipe_in.consume(len(data))
                start_pos = data_cursor
                end_pos = data_cursor + len(data)
                np.testing.assert_array_equal(data,
                                              test_data[start_pos:end_pos])
                data_cursor += len(data)
                run_count += 1

            # make sure the reads are broken up (otherwise test is lame...)
            self.assertGreater(run_count, 2)

        async def runner():
            await asyncio.gather(writer(), reader())
            await npipe_in.close()

        asyncio.run(runner())

    def test_read_data_must_be_consumed(self):
        """writes to pipe sends data to reader and any subscribers"""
        LAYOUT = "float32_2"
        LENGTH = 500
        UNCONSUMED_ROWS = 4
        BUFFER_SIZE = 100
        (fd_r, fd_w) = os.pipe()
        # wrap the file descriptors in numpypipes
        ''
        npipe_in = InputPipe(layout=LAYOUT, reader_factory=reader_factory(fd_r),
                             buffer_size=BUFFER_SIZE)
        npipe_out = OutputPipe(layout=LAYOUT, writer_factory=writer_factory(fd_w))

        test_data = helpers.create_data(LAYOUT, length=LENGTH)

        async def writer():
            await npipe_out.write(test_data)

        async def reader():
            data = await npipe_in.read()
            self.assertLessEqual(len(data), BUFFER_SIZE)
            repeat = await npipe_in.read()
            np.testing.assert_array_equal(data, repeat)
            npipe_in.consume(len(data) - UNCONSUMED_ROWS)

            next_data = await npipe_in.read()

            np.testing.assert_array_equal(data[-UNCONSUMED_ROWS:],
                                          next_data[:UNCONSUMED_ROWS])

        async def runner():
            await asyncio.gather(writer(), reader())
            await npipe_in.close()
            await npipe_out.close()

        asyncio.run(runner())

    def test_raises_consume_errors(self):
        LAYOUT = "float32_2"
        LENGTH = 100
        (fd_r, fd_w) = os.pipe()
        ''
        npipe_in = InputPipe(layout=LAYOUT, reader_factory=reader_factory(fd_r))
        npipe_out = OutputPipe(layout=LAYOUT, writer_factory=writer_factory(fd_w))
        test_data = helpers.create_data(LAYOUT, length=LENGTH)

        # cannot consume more data than is in the pipe

        async def runner():
            await npipe_out.write(test_data)
            read_data = await npipe_in.read()
            await npipe_in.close()
            await npipe_out.close()
            return read_data
        read_data = asyncio.run(runner())

        # can't consume more than was read
        with self.assertRaises(PipeError) as e:
            npipe_in.consume(len(read_data)+1)
        self.assertTrue('consume' in str(e.exception))
        # can't consume less than zero
        with self.assertRaises(PipeError) as e:
            npipe_in.consume(-1)
        # fine to consume zero rows
        npipe_in.consume(0)
        self.assertTrue('negative' in str(e.exception))

    def test_caching(self):
        LAYOUT = "float32_2"
        LENGTH = 128
        CACHE_SIZE = 40
        (fd_r, fd_w) = os.pipe()
        ''
        npipe_in = InputPipe(layout=LAYOUT, reader_factory=reader_factory(fd_r))
        npipe_in.TIMEOUT_INTERVAL = 2
        npipe_out = OutputPipe(layout=LAYOUT, writer_factory=writer_factory(fd_w))
        npipe_out.enable_cache(CACHE_SIZE)
        test_data = helpers.create_data(LAYOUT, length=LENGTH, start=1, step=1)

        async def writer():
            for block in helpers.to_chunks(test_data, 4):
                await asyncio.sleep(.1)
                await npipe_out.write(block)
            await npipe_out.flush_cache()
            # closing the interval should flush the data
            await npipe_out.close_interval()
            # add a dummy section after the interval break
            await npipe_out.write(np.ones((35, 3)))
            # closing the pipe should flush the cache
            await npipe_out.close()

        num_reads = 0

        async def reader():
            nonlocal num_reads
            index = 0
            while True:
                data = await npipe_in.read()
                npipe_in.consume(len(data))
                # make sure the data is correct
                np.testing.assert_array_equal(test_data[index:index+len(data)],
                                              data)
                num_reads += 1
                index += len(data)

                if index == len(test_data):
                    break
            # now get the dummy section after the interval break
            data = await npipe_in.read(flatten=True)
            np.testing.assert_array_equal(data, np.ones((35, 3)))

        async def runner():
            await asyncio.gather(reader(), writer())
            await npipe_in.close()
            await npipe_out.close()
        asyncio.run(runner())
        self.assertLessEqual(num_reads, np.ceil(LENGTH/CACHE_SIZE))


    def test_sends_data_to_subscribers(self):
        LAYOUT = "float32_2"
        (fd_r, fd_w) = os.pipe()
        ''
        output_cb = unittest.mock.AsyncMock()
        input_cb = unittest.mock.AsyncMock()
        subscriber_cb = unittest.mock.AsyncMock()
        npipe_out = OutputPipe(layout=LAYOUT, writer_factory=writer_factory(fd_w),
                               close_cb=output_cb)
        subscriber = LocalPipe(layout=LAYOUT, close_cb=subscriber_cb)
        npipe_out.subscribe(subscriber)
        test_data = helpers.create_data(LAYOUT)
        npipe_in = InputPipe(layout=LAYOUT, reader_factory=reader_factory(fd_r),
                             close_cb=input_cb)
        async def runner():
            await npipe_out.write(test_data)
            rx_data = await npipe_in.read()
            await npipe_in.close()
            await npipe_out.close()
            return rx_data
        rx_data = asyncio.run(runner())
        # data should be available on the InputPipe side

        np.testing.assert_array_equal(test_data, rx_data)
        # data should also be available on the Subscriber output
        rx_data = subscriber.read_nowait()
        np.testing.assert_array_equal(test_data, rx_data)

        # subscriber should be closed
        self.assertTrue(subscriber.closed)
        # make sure all of the callbacks have been executed
        self.assertEqual(output_cb.call_count, 1)
        self.assertEqual(input_cb.call_count, 1)
        self.assertEqual(subscriber_cb.call_count, 1)

    def test_invalid_write_inputs(self):
        LAYOUT = "int8_2"
        ''
        my_pipe = OutputPipe(layout=LAYOUT)

        async def test():
            with self.assertLogs(level="INFO"):
                await my_pipe.write(np.array([[]]))
            with self.assertRaises(PipeError):
                await my_pipe.write(np.array([1, 2, 3]))

        asyncio.run(test())
