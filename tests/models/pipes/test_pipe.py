import asyncio
import numpy as np

from joule.models.pipes import Pipe, PipeError
from tests import helpers


class TestPipe(helpers.AsyncTestCase):

    def test_raises_read_errors(self):
        loop = asyncio.get_event_loop()

        # input pipes must implement read
        pipe = Pipe(direction=Pipe.DIRECTION.INPUT)
        with self.assertRaises(PipeError) as e:
            loop.run_until_complete(pipe.read())
        self.assertTrue("abstract" in "%r" % e.exception)

        # output pipes cannot be read
        pipe = Pipe(direction=Pipe.DIRECTION.OUTPUT)
        with self.assertRaises(PipeError):
            loop.run_until_complete(pipe.read())

    def test_raises_consume_errors(self):
        loop = asyncio.get_event_loop()

        # input pipes must implement consume
        pipe = Pipe(direction=Pipe.DIRECTION.INPUT)
        with self.assertRaises(PipeError) as e:
            loop.run_until_complete(pipe.consume(100))
        self.assertTrue("abstract" in "%r" % e.exception)

        # output pipes cannot be read
        pipe = Pipe(direction=Pipe.DIRECTION.OUTPUT)
        with self.assertRaises(PipeError):
            loop.run_until_complete(pipe.consume(100))

    def test_raises_write_errors(self):
        loop = asyncio.get_event_loop()

        # input pipes cannot write
        pipe = Pipe(direction=Pipe.DIRECTION.INPUT)
        with self.assertRaises(PipeError):
            loop.run_until_complete(pipe.write([1, 2, 3, 4]))

        # output pipes must implement write
        pipe = Pipe(direction=Pipe.DIRECTION.OUTPUT)
        with self.assertRaises(PipeError) as e:
            loop.run_until_complete(pipe.write([1, 2, 3, 4]))
        self.assertTrue("abstract" in "%r" % e.exception)

    def test_raises_cache_errors(self):
        loop = asyncio.get_event_loop()
        # input pipes cannot cache
        pipe = Pipe(direction=Pipe.DIRECTION.INPUT)
        with self.assertRaises(PipeError):
            pipe.enable_cache(100)
        with self.assertRaises(PipeError):
            loop.run_until_complete(pipe.flush_cache())

        # output pipes must implement caching
        pipe = Pipe(direction=Pipe.DIRECTION.OUTPUT)
        with self.assertRaises(PipeError) as e:
            pipe.enable_cache(100)
        self.assertTrue("abstract" in "%r" % e.exception)
        with self.assertRaises(PipeError):
            loop.run_until_complete(pipe.flush_cache())
        self.assertTrue("abstract" in "%r" % e.exception)

    def test_raises_close_interval_errors(self):
        loop = asyncio.get_event_loop()

        # input pipes cannot close intervals
        pipe = Pipe(direction=Pipe.DIRECTION.INPUT)
        with self.assertRaises(PipeError):
            loop.run_until_complete(pipe.close_interval())

        # output pipes must implement close_interval
        pipe = Pipe(direction=Pipe.DIRECTION.OUTPUT)
        with self.assertRaises(PipeError) as e:
            loop.run_until_complete(pipe.close_interval())
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
