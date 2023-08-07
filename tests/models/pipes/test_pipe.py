import asyncio
import numpy as np

from joule.models.pipes import Pipe, PipeError, LocalPipe
from tests import helpers


class TestPipe(helpers.AsyncTestCase):

    def test_raises_read_errors(self):
        ''

        # input pipes must implement read
        pipe = Pipe(direction=Pipe.DIRECTION.INPUT)
        with self.assertRaises(PipeError) as e:
            asyncio.run(pipe.read())
        self.assertTrue("abstract" in "%r" % e.exception)

        # output pipes cannot be read
        pipe = Pipe(direction=Pipe.DIRECTION.OUTPUT)
        with self.assertRaises(PipeError):
            asyncio.run(pipe.read())

    def test_raises_consume_errors(self):
        ''

        # input pipes must implement consume
        pipe = Pipe(direction=Pipe.DIRECTION.INPUT)
        with self.assertRaises(PipeError) as e:
            asyncio.run(pipe.consume(100))
        self.assertTrue("abstract" in "%r" % e.exception)

        # output pipes cannot be read
        pipe = Pipe(direction=Pipe.DIRECTION.OUTPUT)
        with self.assertRaises(PipeError):
            asyncio.run(pipe.consume(100))

    def test_raises_write_errors(self):
        ''

        # input pipes cannot write
        pipe = Pipe(direction=Pipe.DIRECTION.INPUT)
        with self.assertRaises(PipeError):
            asyncio.run(pipe.write(np.array([1, 2, 3, 4])))

        # output pipes must implement write
        pipe = Pipe(direction=Pipe.DIRECTION.OUTPUT)
        with self.assertRaises(PipeError) as e:
            asyncio.run(pipe.write(np.array([1, 2, 3, 4])))
        self.assertTrue("abstract" in "%r" % e.exception)

    def test_raises_cache_errors(self):
        ''
        # input pipes cannot cache
        pipe = Pipe(direction=Pipe.DIRECTION.INPUT)
        with self.assertRaises(PipeError):
            pipe.enable_cache(100)
        with self.assertRaises(PipeError):
            asyncio.run(pipe.flush_cache())

        # output pipes must implement caching
        pipe = Pipe(direction=Pipe.DIRECTION.OUTPUT)
        with self.assertRaises(PipeError) as e:
            pipe.enable_cache(100)
        self.assertTrue("abstract" in "%r" % e.exception)
        with self.assertRaises(PipeError):
            asyncio.run(pipe.flush_cache())
        self.assertTrue("abstract" in "%r" % e.exception)

    def test_raises_close_interval_errors(self):
        ''

        # input pipes cannot close intervals
        pipe = Pipe(direction=Pipe.DIRECTION.INPUT)
        with self.assertRaises(PipeError):
            asyncio.run(pipe.close_interval())

        # output pipes must implement close_interval
        pipe = Pipe(direction=Pipe.DIRECTION.OUTPUT)
        with self.assertRaises(PipeError) as e:
            asyncio.run(pipe.close_interval())
        self.assertTrue("abstract" in "%r" % e.exception)

    def test_checks_dtype(self):
        for layout in ['invalid', 'bad_3', 'float_abc']:
            pipe = Pipe(layout=layout)
            with self.assertRaises(ValueError) as e:
                _ = pipe.dtype
            self.assertTrue("layout" in "%r" % e.exception)

    def test_end_of_interval_default(self):
        # end of interval flag is false by default
        pipe = Pipe(direction=Pipe.DIRECTION.INPUT)
        self.assertFalse(pipe.end_of_interval)

    def test_raises_dtype_errors(self):
        pipe = Pipe(layout="uint8_4")
        # data for a different stream type
        data1 = helpers.create_data("float32_3")
        # invalid array structure (must be 2D)
        data2 = np.ones((3, 3, 3))
        # invalid structured array
        data3 = np.array([('timestamp', 1, 2, 3), ('bad', 1, 2, 3)])
        for data in [data1, data2, data3]:
            with self.assertRaises(PipeError):
                _ = pipe._apply_dtype(data)

    def test_subscribe(self):
        LAYOUT = "uint8_4"
        # cannot subscribe to input pipes
        input_pipe = Pipe(layout=LAYOUT, direction=Pipe.DIRECTION.INPUT)
        output_pipe = Pipe(layout=LAYOUT, direction=Pipe.DIRECTION.OUTPUT)
        subscriber = Pipe(layout=LAYOUT, direction=Pipe.DIRECTION.OUTPUT)
        with self.assertRaises(PipeError):
            input_pipe.subscribe(subscriber)
        # can subscribe to output pipes
        unsubscribe = output_pipe.subscribe(subscriber)
        self.assertIn(subscriber, output_pipe.subscribers)
        # can unsubscribe
        unsubscribe()
        self.assertNotIn(subscriber, output_pipe.subscribers)

    def test_read_all_flatten(self):
        asyncio.run(self._test_read_all_flatten())

    async def _test_read_all_flatten(self):
        # This test is a bit tricky because it needs to run in an unbroken
        # event loop since it creates LocalPipes outside of the test
        LAYOUT = "int32_3"
        LENGTH = 1000
        ''

        # raises exception if the pipe is empty
        my_pipe = LocalPipe(LAYOUT, name="pipe")
        my_pipe.close_nowait()
        with self.assertRaises(PipeError):
            await my_pipe.read_all(flatten=True)
        # read_all empties pipe and closes it, regardless of intervals
        my_pipe = LocalPipe(LAYOUT, name="pipe")
        test_data1 = helpers.create_data(LAYOUT, length=LENGTH)
        test_data2 = helpers.create_data(LAYOUT, length=LENGTH)
        my_pipe.write_nowait(test_data1)
        my_pipe.close_interval_nowait()
        my_pipe.write_nowait(test_data2)
        my_pipe.close_nowait()
        actual_data = await my_pipe.read_all(flatten=True)
        expected_data = np.hstack((test_data1, test_data2))
        expected_data = np.c_[expected_data['timestamp'][:, None], expected_data['data']]
        np.testing.assert_array_equal(actual_data, expected_data)
        self.assertTrue(my_pipe.closed)

        # read_all only add maxrows to the pipe
        # (less than one read)
        my_pipe = LocalPipe(LAYOUT, name="pipe")
        test_data1 = helpers.create_data(LAYOUT, length=LENGTH)
        test_data2 = helpers.create_data(LAYOUT, length=LENGTH)
        my_pipe.write_nowait(test_data1)
        my_pipe.close_interval_nowait()
        my_pipe.write_nowait(test_data2)
        actual_data = await my_pipe.read_all(maxrows=103, flatten=True)
        expected_data = test_data1[:103]
        expected_data = np.c_[expected_data['timestamp'][:, None], expected_data['data']]
        np.testing.assert_array_equal(actual_data, expected_data)
        self.assertTrue(my_pipe.closed)
        # (more than one read)
        my_pipe = LocalPipe(LAYOUT, name="pipe")
        test_data1 = helpers.create_data(LAYOUT, length=LENGTH)
        test_data2 = helpers.create_data(LAYOUT, length=LENGTH)
        my_pipe.write_nowait(test_data1)
        my_pipe.close_interval_nowait()
        my_pipe.write_nowait(test_data2)
        actual_data = await my_pipe.read_all(maxrows=LENGTH + 101, flatten=True)
        expected_data = np.hstack((test_data1, test_data2[:101]))
        expected_data = np.c_[expected_data['timestamp'][:, None], expected_data['data']]
        np.testing.assert_array_equal(expected_data, actual_data)
        self.assertTrue(my_pipe.closed)

        # read_all raises an exception if the pipe has more than maxrows
        # (less than one read)
        my_pipe = LocalPipe(LAYOUT, name="pipe")
        test_data1 = helpers.create_data(LAYOUT, length=LENGTH)
        test_data2 = helpers.create_data(LAYOUT, length=LENGTH)
        my_pipe.write_nowait(test_data1)
        my_pipe.close_interval_nowait()
        my_pipe.write_nowait(test_data2)
        with self.assertRaises(PipeError):
            await my_pipe.read_all(maxrows=LENGTH + 101,
                                                     error_on_overflow=True, flatten=True)
        self.assertTrue(my_pipe.closed)
        # (more than one read)
        my_pipe = LocalPipe(LAYOUT, name="pipe")
        test_data1 = helpers.create_data(LAYOUT, length=LENGTH)
        test_data2 = helpers.create_data(LAYOUT, length=LENGTH)
        my_pipe.write_nowait(test_data1)
        my_pipe.close_interval_nowait()
        my_pipe.write_nowait(test_data2)
        my_pipe.close_nowait()
        with self.assertRaises(PipeError):
            await my_pipe.read_all(maxrows=LENGTH + 101,
                                                     error_on_overflow=True, flatten=True)
        self.assertTrue(my_pipe.closed)

    def test_read_all_no_flatten(self):
        asyncio.run(self._test_read_all_no_flatten())

    async def _test_read_all_no_flatten(self):
        LAYOUT = "int32_3"
        LENGTH = 1000
        ''

        # raises exception if the pipe is empty
        my_pipe = LocalPipe(LAYOUT, name="pipe")
        my_pipe.close_nowait()
        with self.assertRaises(PipeError):
            await my_pipe.read_all()

        # read_all empties pipe and closes it, regardless of intervals
        my_pipe = LocalPipe(LAYOUT, name="pipe")
        test_data1 = helpers.create_data(LAYOUT, length=LENGTH)
        test_data2 = helpers.create_data(LAYOUT, length=LENGTH)
        my_pipe.write_nowait(test_data1)
        my_pipe.close_interval_nowait()
        my_pipe.write_nowait(test_data2)
        my_pipe.close_nowait()
        actual_data = await my_pipe.read_all()
        expected_data = np.hstack((test_data1, test_data2))
        np.testing.assert_array_equal(actual_data, expected_data)
        self.assertTrue(my_pipe.closed)

        # read_all only add maxrows to the pipe
        # (less than one read)
        my_pipe = LocalPipe(LAYOUT, name="pipe")
        test_data1 = helpers.create_data(LAYOUT, length=LENGTH)
        test_data2 = helpers.create_data(LAYOUT, length=LENGTH)
        my_pipe.write_nowait(test_data1)
        my_pipe.close_interval_nowait()
        my_pipe.write_nowait(test_data2)
        actual_data = await my_pipe.read_all(maxrows=103)
        expected_data = test_data1[:103]
        np.testing.assert_array_equal(actual_data, expected_data)
        self.assertTrue(my_pipe.closed)
        # (more than one read)
        my_pipe = LocalPipe(LAYOUT, name="pipe")
        test_data1 = helpers.create_data(LAYOUT, length=LENGTH)
        test_data2 = helpers.create_data(LAYOUT, length=LENGTH)
        my_pipe.write_nowait(test_data1)
        my_pipe.close_interval_nowait()
        my_pipe.write_nowait(test_data2)
        actual_data = await my_pipe.read_all(maxrows=LENGTH + 101)
        expected_data = np.hstack((test_data1, test_data2[:101]))
        np.testing.assert_array_equal(expected_data, actual_data)
        self.assertTrue(my_pipe.closed)

        # read_all raises an exception if the pipe has more than maxrows
        # (less than one read)
        my_pipe = LocalPipe(LAYOUT, name="pipe")
        test_data1 = helpers.create_data(LAYOUT, length=LENGTH)
        test_data2 = helpers.create_data(LAYOUT, length=LENGTH)
        my_pipe.write_nowait(test_data1)
        my_pipe.close_interval_nowait()
        my_pipe.write_nowait(test_data2)
        with self.assertRaises(PipeError):
            await my_pipe.read_all(maxrows=LENGTH + 101, error_on_overflow=True)
        self.assertTrue(my_pipe.closed)
        # (more than one read)
        my_pipe = LocalPipe(LAYOUT, name="pipe")
        test_data1 = helpers.create_data(LAYOUT, length=LENGTH)
        test_data2 = helpers.create_data(LAYOUT, length=LENGTH)
        my_pipe.write_nowait(test_data1)
        my_pipe.close_interval_nowait()
        my_pipe.write_nowait(test_data2)
        my_pipe.close_nowait()
        with self.assertRaises(PipeError):
            await my_pipe.read_all(maxrows=LENGTH + 101, error_on_overflow=True)
        self.assertTrue(my_pipe.closed)
