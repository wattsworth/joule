import unittest
import asyncio
import numpy as np

from joule.models.pipes import LocalPipe, PipeError, OutputPipe
from tests import helpers
from joule.errors import EmptyPipeError


class TestLocalPipeBasicOperation(unittest.TestCase):
    def test_normal_operation(self):
        # running through the data, each element is returned once
        # every call to read returns some data or an EmptyPipe error
        async def _run():
            LAYOUT = "float32_3"
            LENGTH = 100
            pipe = LocalPipe(layout="float32_3")
            tx_data = helpers.create_data(LAYOUT, length=LENGTH)
            # write a block and close off the pipe
            await pipe.write(tx_data)
            await pipe.close()
            # read it back
            rx_data = await pipe.read()
            np.testing.assert_array_equal(tx_data, rx_data)
            # don't consume it so you can read it agai
            pipe.consume(len(rx_data[:500]))
            # read it back again
            rx_data = await pipe.read()
            np.testing.assert_array_equal(tx_data[500:], rx_data)
            # the pipe should be empty now
            self.assertTrue(pipe.is_empty())
            with self.assertRaises(EmptyPipeError):
                await pipe.read()
