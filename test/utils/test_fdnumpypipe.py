
import asynctest
from joule.utils.stream_numpypipe_reader import StreamNumpyPipeReader
from joule.utils.stream_numpypipe_writer import StreamNumpyPipeWriter
import joule.utils.fd_factory as fd_factory
import os
import numpy as np
import asyncio
from test import helpers

"""
Tests NumpyPipes with subprocess pipes 
"""


class TestNumpyPipe(asynctest.TestCase):

    def test_pipes_numpy_arrays(self):
        LAYOUT = "int8_2"
        LENGTH = 1000
        (fd_r, fd_w) = os.pipe()

        npipe_in = StreamNumpyPipeReader(LAYOUT,
                                         fd_factory.reader_factory(fd_r))
        npipe_out = StreamNumpyPipeWriter(LAYOUT,
                                          fd_factory.writer_factory(fd_w))
        test_data = helpers.create_data(LAYOUT, length=LENGTH)


        async def writer():
            for block in helpers.to_chunks(test_data, 270):
                await npipe_out.write(block)
                await asyncio.sleep(0.01)

        async def reader():
            blk_size = 357
            data_cursor = 0  # index into test_data
            run_count = 0
            while(data_cursor != len(test_data)):
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

        tasks = [asyncio.ensure_future(writer()),
                 asyncio.ensure_future(reader())]
        loop = asyncio.get_event_loop()
        loop.run_until_complete(asyncio.gather(*tasks))

        npipe_in.close()
        npipe_out.close()

    def test_reconstructs_fragmented_data(self):
        LAYOUT = "int8_2"
        LENGTH = 1000
        (fd_r, fd_w) = os.pipe()

        # wrap the file descriptors in numpypipes
        npipe_in = StreamNumpyPipeReader(LAYOUT,
                                         fd_factory.reader_factory(fd_r))
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
            while(data_cursor != len(test_data)):
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

        tasks = [asyncio.ensure_future(writer()),
                 asyncio.ensure_future(reader())]
        loop = asyncio.get_event_loop()
        loop.run_until_complete(asyncio.gather(*tasks))
        npipe_in.close()

    def test_read_data_must_be_consumed(self):
        """writes to pipe sends data to reader and any subscribers"""
        LAYOUT = "float32_2"
        LENGTH = 500
        UNCONSUMED_ROWS = 4
        (fd_r, fd_w) = os.pipe()
        # wrap the file descriptors in numpypipes
        npipe_in = StreamNumpyPipeReader(LAYOUT,
                                         fd_factory.reader_factory(fd_r),
                                         buffer_size=100)
        npipe_out = StreamNumpyPipeWriter(LAYOUT,
                                          fd_factory.writer_factory(fd_w))
        
        test_data = helpers.create_data(LAYOUT, length=LENGTH)

        async def writer():
            await npipe_out.write(test_data)

        async def reader():
            data = await npipe_in.read()
            npipe_in.consume(len(data) - UNCONSUMED_ROWS)
            next_data = await npipe_in.read()

            np.testing.assert_array_equal(data[-UNCONSUMED_ROWS:],
                                          next_data[:UNCONSUMED_ROWS])

        tasks = [asyncio.ensure_future(writer()),
                 asyncio.ensure_future(reader())]
        loop = asyncio.get_event_loop()
        loop.run_until_complete(asyncio.gather(*tasks))

        npipe_in.close()
        npipe_out.close()
