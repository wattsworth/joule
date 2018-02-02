from joule import FilterModule
import asyncio
import io
import asynctest
import unittest
import tempfile
import os
import shutil
import argparse
from contextlib import redirect_stdout

MODULE_CONFIG = """
[Main]
  name = test
  exec_cmd = ignored
[Inputs]
  input = /myfilter/input
[Outputs]
  dest1 = /myfilter/dest1
  dest2 = /myfilter/dest2
"""

STREAM_CONFIGS = [
    """
[Main]
  name = input
  path = /myfilter/input
  datatype = float32
  decimate = yes
  keep = 1w
[Element1]
  name = e1
    """,
    """
[Main]
  name = dest1
  path = /myfilter/dest1
  datatype = float32
  decimate = yes
  keep = 1w
[Element1]
  name = e1
    """,
    """
[Main]
  name = dest2
  path = /myfilter/dest2
  datatype = float32
  decimate = yes
  keep = 1w
[Element1]
  name = e
    """]


"""
When run from the command line a filter can request
pipes from the local jouled instance
"""


class TestFilterDebugMode(unittest.TestCase):

    def setUp(self):

        # build the module config and stream config dir
        self.module_config = tempfile.NamedTemporaryFile(delete=False,
                                                         suffix=".conf").name
        with open(self.module_config, 'w') as f:
            for line in MODULE_CONFIG:
                f.write(line)
        # build the stream config dir
        self.stream_config_dir = tempfile.mkdtemp()
        for config in STREAM_CONFIGS:
            (fd, path) = tempfile.mkstemp(dir=self.stream_config_dir,
                                          suffix=".conf")
            with open(fd, 'w') as f:
                for line in config:
                    f.write(line)

    def tearDown(self):
        os.remove(self.module_config)
        shutil.rmtree(self.stream_config_dir)

    @asynctest.patch("joule.client.base_module.request_reader")
    @asynctest.patch("joule.client.base_module.request_writer")
    def test_builds_networked_streams(self, mock_writer, mock_reader):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        myfilter = FilterModule()
        args = argparse.Namespace(
            pipes="unset",
            start_time=None,
            end_time=None,
            module_config=self.module_config,
            stream_configs=self.stream_config_dir)
        
        myfilter.run = asynctest.CoroutineMock()
        f = io.StringIO()
        with redirect_stdout(f):
            myfilter.start(parsed_args=args)
        # check to make sure the run function is called with pipes
        args, kwargs = myfilter.run.call_args
        inputs = args[1]
        outputs = args[2]
        self.assertTrue('input' in inputs)
        self.assertTrue('dest1' in outputs)
        self.assertTrue('dest2' in outputs)

