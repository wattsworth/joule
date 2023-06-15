from joule import LocalPipe
import asyncio
import numpy as np
import argparse
import tempfile
import os
import time

from tests import helpers
from joule.client.builtins.file_reader import FileReader

WIDTH = 3


class TestFileReader(helpers.AsyncTestCase):

    def test_reads_timestamped_values(self):
        data = helpers.create_data("float32_8", length=3)
        (data_file, path) = tempfile.mkstemp()
        with open(data_file, 'w') as f:
            for row in data:
                f.write("%d %s\n" % (row['timestamp'], ' '.join(repr(x) for x in row['data'])))
        my_reader = FileReader()
        ''
        pipe = LocalPipe("float32_8", name="output")
        args = argparse.Namespace(file=path, delimiter=" ",
                                  timestamp=False)
        asyncio.run(my_reader.run(args, pipe))
        # check the results
        result = pipe.read_nowait()
        np.testing.assert_array_almost_equal(data['timestamp'], result['timestamp'])
        np.testing.assert_array_almost_equal(data['data'], result['data'])
        os.remove(path)

    def test_timestamps_raw_values(self):
        data = helpers.create_data("float32_8", length=3)
        (data_file, path) = tempfile.mkstemp()
        with open(data_file, 'w') as f:
            for row in data:
                f.write("%s\n" % ' '.join(repr(x) for x in row['data']))
        my_reader = FileReader()
        ''
        pipe = LocalPipe("float32_8", name="output")
        args = argparse.Namespace(file=path, delimiter=" ",
                                  timestamp=True)
        asyncio.run(my_reader.run(args, pipe))
        # check the results
        result = pipe.read_nowait()
        # timestamps should be close to now
        actual = np.average(result['timestamp'])
        expected = int(time.time() * 1e6)
        # should be within 1 second
        np.testing.assert_almost_equal(actual / 1e6, expected / 1e6, decimal=0)
        np.testing.assert_array_almost_equal(data['data'], result['data'])
        os.remove(path)

    def test_stops_on_request(self):
        data = helpers.create_data("float32_8")
        (data_file, path) = tempfile.mkstemp()
        with open(data_file, 'w') as f:
            for row in data:
                f.write("%d %s\n" % (row['timestamp'], ' '.join(repr(x) for x in row['data'])))
        my_reader = FileReader()
        ''
        pipe = LocalPipe("float32_8", name="output")
        args = argparse.Namespace(file=path, delimiter=" ",
                                  timestamp=False)
        my_reader.stop()
        asyncio.run(my_reader.run(args, pipe))
        # check the results
        result = pipe.read_nowait()

        # output should be shorter than the input
        self.assertLess(len(result), len(data))
        os.remove(path)
