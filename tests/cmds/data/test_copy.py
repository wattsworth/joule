import unittest
from click.testing import CliRunner
import os
import signal
import multiprocessing
from aiohttp.test_utils import unused_port
import warnings
import traceback
import pdb
import numpy as np

from ..fake_joule import FakeJoule
from joule.cli import main
from joule.models import Stream, Element, StreamInfo
from tests import helpers

STREAM_LIST = os.path.join(os.path.dirname(__file__), 'streams.json')
warnings.simplefilter('always')


class TestDataCopy(unittest.TestCase):

    def start_server(self, server):
        port = unused_port()
        self.msgs = multiprocessing.Queue()
        self.server_proc = multiprocessing.Process(target=server.start, args=(port, self.msgs))
        self.server_proc.start()
        return "http://localhost:%d" % port

    def stop_server(self):
        if self.server_proc is None:
            return
        # aiohttp doesn't always quit with SIGTERM
        os.kill(self.server_proc.pid, signal.SIGKILL)
        # join any zombies
        multiprocessing.active_children()
        self.server_proc.join()

    def test_copies_data(self):
        server = FakeJoule()
        # create the source and destination streams
        src = Stream(id=0, name="source", keep_us=100, datatype=Stream.DATATYPE.FLOAT32)
        src.elements = [Element(name="e%d" % x, index=x, display_type=Element.DISPLAYTYPE.CONTINUOUS) for x in range(3)]
        dest = Stream(id=1, name="dest", keep_us=100, datatype=Stream.DATATYPE.FLOAT32)
        dest.elements = [Element(name="e%d" % x, index=x, display_type=Element.DISPLAYTYPE.CONTINUOUS) for x in
                         range(3)]
        # source has 100 rows of data between [0, 100]
        src_data = helpers.create_data(src.layout)
        src_info = StreamInfo(int(src_data['timestamp'][0]), int(src_data['timestamp'][-1]), len(src_data))
        server.add_stream('/test/source', src, src_info, src_data)
        # dest is empty
        server.add_stream('/test/destination', dest, StreamInfo(None, None, 0), None)

        url = self.start_server(server)
        runner = CliRunner()
        result = runner.invoke(main, ['--url', url, 'data', 'copy', '/test/source', '/test/destination'])
        self.assertEqual(result.exit_code, 0)
        mock_entry = self.msgs.get()
        np.testing.assert_array_equal(src_data, mock_entry.data)
        self.stop_server()

    def test_when_server_is_not_available(self):
        url = "http://127.0.0.1:%d" % unused_port()
        runner = CliRunner()
        result = runner.invoke(main, ['--url', url, 'data', 'copy'])
        self.assertTrue('Error' in result.output)
        # self.assertEqual(result.exit_code, 1)

    @unittest.skip("TODO")
    def test_when_server_returns_invalid_data(self):
        server = FakeJoule()
        server.stream_list_response = "notjson"
        url = self.start_server(server)
        runner = CliRunner()
        result = runner.invoke(main, ['--url', url, 'data', 'copy'])
        self.assertTrue('Error' in result.output)
        self.assertEqual(result.exit_code, 1)
        self.stop_server()

    @unittest.skip("TODO")
    def test_when_server_returns_error_code(self):
        server = FakeJoule()
        error_msg = "test error"
        error_code = 500
        server.stream_list_response = error_msg
        server.stream_list_code = error_code
        url = self.start_server(server)
        runner = CliRunner()
        result = runner.invoke(main, ['--url', url, 'stream', 'list'])
        self.assertTrue('%d' % error_code in result.output)
        self.assertTrue(error_msg in result.output)
        self.assertEqual(result.exit_code, 1)
        self.stop_server()
