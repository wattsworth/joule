from joule import LocalPipe
import asyncio
import numpy as np
import argparse
import tempfile
import os

from tests import helpers
from joule.client.builtins.file_reader import FileReader

WIDTH = 3


class TestFileReader(helpers.AsyncTestCase):

    def test_reads_timestamped_values(self):
        data = helpers.create_data("float32_8")
        (data_file, path) = tempfile.mkstemp()
        with open(data_file, 'w') as f:
            for row in data:
                f.write("%d %s\n" % (row['timestamp'], ' '.join(repr(x) for x in row['data'])))
        my_reader = FileReader()
        loop = asyncio.get_event_loop()
        pipe = LocalPipe("float32_8", loop, name="output")
        args = argparse.Namespace(file=path, delimiter=" ",
                                  timestamp=False)
        loop.run_until_complete(my_reader.run(args, pipe))
        # check the results
        result = pipe.read_nowait()
        np.testing.assert_array_almost_equal(data['timestamp'], result['timestamp'])
        np.testing.assert_array_almost_equal(data['data'], result['data'])
        os.remove(path)
