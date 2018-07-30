from click.testing import CliRunner
import os
import signal
import multiprocessing
from aiohttp.test_utils import unused_port
import warnings
import time
import numpy as np

from ..fake_joule import FakeJoule
from joule.cli import main
from joule.models import Stream, Element, StreamInfo, pipes
from tests import helpers

warnings.simplefilter('always')


class TestDataCopy(helpers.AsyncTestCase):

    def start_server(self, server):
        port = unused_port()
        self.msgs = multiprocessing.Queue()
        self.server_proc = multiprocessing.Process(target=server.start, args=(port, self.msgs))
        self.server_proc.start()
        time.sleep(0.01)
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
        src_data = create_source_data(server)  # helpers.create_data(src.layout)
        # dest is empty
        dest = Stream(id=1, name="dest", keep_us=100, datatype=Stream.DATATYPE.FLOAT32)
        dest.elements = [Element(name="e%d" % x, index=x, display_type=Element.DISPLAYTYPE.CONTINUOUS) for x in
                         range(3)]
        server.add_stream('/test/destination', dest, StreamInfo(None, None, 0), None)

        url = self.start_server(server)
        runner = CliRunner()
        result = runner.invoke(main, ['--url', url, 'data', 'copy', '/test/source', '/test/destination'])
        self.assertEqual(result.exit_code, 0)
        mock_entry = self.msgs.get()
        np.testing.assert_array_equal(src_data, mock_entry.data)
        self.assertEqual(mock_entry.n_intervals, 3)
        self.stop_server()

    def test_creates_stream_if_necessary(self):
        server = FakeJoule()
        # create the source stream
        src = Stream(id=0, name="source", keep_us=100, datatype=Stream.DATATYPE.FLOAT32)
        src.elements = [Element(name="e%d" % x, index=x, display_type=Element.DISPLAYTYPE.CONTINUOUS) for x in range(3)]

        # source has 100 rows of data between [0, 100]
        src_data = helpers.create_data(src.layout, length=4)
        src_info = StreamInfo(int(src_data['timestamp'][0]), int(src_data['timestamp'][-1]), len(src_data))
        server.add_stream('/test/source', src, src_info, src_data)

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
        result = runner.invoke(main, ['--url', url, 'data', 'copy', '/test/source', '/test/destination'])
        self.assertTrue('Error' in result.output)
        self.assertEqual(result.exit_code, 1)

    def test_when_source_is_empty(self):
        server = FakeJoule()
        # source has no data
        src_info = StreamInfo(None, None, 0)
        # create the source stream
        src = Stream(id=0, name="source", keep_us=100, datatype=Stream.DATATYPE.FLOAT32)
        src.elements = [Element(name="e%d" % x, index=x, display_type=Element.DISPLAYTYPE.CONTINUOUS) for x in range(3)]
        server.add_stream('/test/source', src, src_info, np.ndarray([]))
        url = self.start_server(server)
        runner = CliRunner()
        result = runner.invoke(main, ['--url', url, 'data', 'copy', '/test/source', '/test/destination'])
        self.assertTrue('Error' in result.output and 'source' in result.output)
        self.assertEqual(result.exit_code, 1)
        self.stop_server()

    def test_when_destination_is_invalid(self):
        server = FakeJoule()
        # create the source stream
        src = Stream(id=0, name="source", keep_us=100, datatype=Stream.DATATYPE.FLOAT32)
        src.elements = [Element(name="e%d" % x, index=x, display_type=Element.DISPLAYTYPE.CONTINUOUS) for x in range(3)]

        # source has 100 rows of data between [0, 100]
        src_data = helpers.create_data(src.layout, length=4)
        src_info = StreamInfo(int(src_data['timestamp'][0]), int(src_data['timestamp'][-1]), len(src_data))

        server.add_stream('/test/source', src, src_info, np.ndarray([]))
        url = self.start_server(server)
        runner = CliRunner()
        result = runner.invoke(main, ['--url', url, 'data', 'copy', '/test/source', 'badpath'])
        self.assertTrue('Error' in result.output and 'destination' in result.output)
        self.assertEqual(result.exit_code, 1)
        self.stop_server()

    def test_when_server_returns_invalid_data(self):
        server = FakeJoule()
        create_source_data(server)

        server.response = "notjson"
        server.http_code = 200
        url = self.start_server(server)
        runner = CliRunner()
        result = runner.invoke(main, ['--url', url, 'data', 'copy', '/test/source', '/stub/response'])
        self.assertTrue('Error' in result.output)

        self.assertEqual(result.exit_code, 1)
        self.stop_server()

    def test_incompatible_layouts(self):
        server = FakeJoule()
        create_source_data(server)
        dest = Stream(id=1, name="dest", keep_us=100, datatype=Stream.DATATYPE.FLOAT32)
        dest.elements = [Element(name="e%d" % x, index=x, display_type=Element.DISPLAYTYPE.CONTINUOUS) for x in
                         range(5)]
        server.add_stream('/test/destination', dest, StreamInfo(None, None, 0), None)
        url = self.start_server(server)
        runner = CliRunner()
        result = runner.invoke(main, ['--url', url, 'data', 'copy', '/test/source', '/test/destination'])
        self.assertTrue('not compatible' in result.output)
        self.assertEqual(result.exit_code, 1)
        self.stop_server()

    def test_warn_on_different_elements(self):
        server = FakeJoule()
        create_source_data(server)
        dest = Stream(id=1, name="dest", keep_us=100, datatype=Stream.DATATYPE.FLOAT32)
        dest.elements = [
            Element(name="different%d" % x, index=x, units='other', display_type=Element.DISPLAYTYPE.CONTINUOUS) for x
            in
            range(3)]
        server.add_stream('/test/destination', dest, StreamInfo(None, None, 0), None)
        url = self.start_server(server)
        runner = CliRunner()
        # does not copy without confirmation
        result = runner.invoke(main, ['--url', url, 'data', 'copy', '/test/source', '/test/destination'])
        self.assertTrue(self.msgs.empty())
        self.assertNotEqual(result.exit_code, 0)
        # copies with confirmation
        result = runner.invoke(main, ['--url', url, 'data', 'copy', '/test/source', '/test/destination'],
                               input='y\n')
        mock_entry = self.msgs.get()
        self.assertTrue(len(mock_entry.data) > 0)
        self.assertEqual(result.exit_code, 0)
        self.stop_server()

    def test_start_must_be_before_end(self):
        server = FakeJoule()
        create_source_data(server)
        url = self.start_server(server)
        runner = CliRunner()
        # does not copy without confirmation
        result = runner.invoke(main, ['--url', url, 'data', 'copy',
                                      '/test/source', '/test/destination',
                                      '--start', '1 hour ago', '--end', '2 hours ago'])
        self.assertEqual(result.exit_code, 1)
        self.assertTrue('start' in result.output and 'end' in result.output)
        self.stop_server()

    def test_data_read_errors(self):
        server = FakeJoule()
        server.stub_data_read = True
        server.http_code = 400
        server.response = 'nilmdb error'
        create_source_data(server)
        url = self.start_server(server)
        runner = CliRunner()
        result = runner.invoke(main, ['--url', url, 'data', 'copy',
                                      '/test/source', '/test/destination'])
        self.assertEqual(result.exit_code, 1)
        self.assertTrue('Error' in result.output and 'source' in result.output)
        self.stop_server()

    def test_data_write_errors(self):
        server = FakeJoule()
        server.stub_data_write = True
        server.http_code = 400
        server.response = 'nilmdb error'
        create_source_data(server)
        url = self.start_server(server)
        runner = CliRunner()
        result = runner.invoke(main, ['--url', url, 'data', 'copy',
                                      '/test/source', '/test/destination'])
        self.assertEqual(result.exit_code, 1)
        self.assertTrue('Error' in result.output and 'destination' in result.output)
        self.stop_server()


def create_source_data(server):
    # create the source stream
    src = Stream(id=0, name="source", keep_us=100, datatype=Stream.DATATYPE.FLOAT32)
    src.elements = [Element(name="e%d" % x, index=x, display_type=Element.DISPLAYTYPE.CONTINUOUS) for x in range(3)]

    # source has 100 rows of data in four intervals between [0, 100]
    src_data = helpers.create_data(src.layout, length=100, start=0, step=1)
    # insert the intervals
    pipe_data = np.hstack((src_data[:25],
                           pipes.interval_token(src.layout),
                           src_data[25:50],
                           pipes.interval_token(src.layout),
                           src_data[50:75],
                           pipes.interval_token(src.layout),
                           src_data[75:]))
    src_info = StreamInfo(int(src_data['timestamp'][0]), int(src_data['timestamp'][-1]), len(src_data))
    server.add_stream('/test/source', src, src_info, pipe_data)
    return src_data
