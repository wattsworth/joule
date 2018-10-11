from click.testing import CliRunner
from aiohttp.test_utils import unused_port
import warnings
import numpy as np

from ..fake_joule import FakeJoule, FakeJouleTestCase
from joule.cli import main
from joule.models import Stream, Element, StreamInfo, pipes
from tests import helpers

warnings.simplefilter('always')


class TestDataCopy(FakeJouleTestCase):

    def test_copies_all_data(self):
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
        _print_result_on_error(result)
        self.assertEqual(result.exit_code, 0)
        mock_entry = self.msgs.get()
        np.testing.assert_array_equal(src_data, mock_entry.data)
        #self.assertEqual(len(mock_entry.intervals), 3)
        self.stop_server()

    def test_does_not_copy_existing_data(self):
        server = FakeJoule()
        # create the source and destination streams
        src_data = create_source_data(server)  # helpers.create_data(src.layout)
        # dest has the same intervals as source so nothing is copied
        ts = src_data['timestamp']
        intervals = server.streams['/test/source'].intervals

        dest = Stream(id=1, name="dest", keep_us=100, datatype=Stream.DATATYPE.FLOAT32)
        dest.elements = [Element(name="e%d" % x, index=x, display_type=Element.DISPLAYTYPE.CONTINUOUS) for x in
                         range(3)]
        server.add_stream('/test/destination', dest, StreamInfo(int(ts[0]), int(ts[-1]),
                                                                len(ts)), src_data, intervals)
        url = self.start_server(server)
        runner = CliRunner()
        result = runner.invoke(main, ['--url', url, 'data', 'copy',
                                      '--start', str(ts[0]), '--end', str(ts[-1]),
                                      '/test/source', '/test/destination'])
        _print_result_on_error(result)
        self.assertEqual(result.exit_code, 0)
        # data write was never called
        self.assertTrue(self.msgs.empty())
        self.stop_server()

    def test_creates_stream_if_necessary(self):
        server = FakeJoule()
        # create the source stream
        src = Stream(id=0, name="source", keep_us=100, datatype=Stream.DATATYPE.FLOAT32)
        src.elements = [Element(name="e%d" % x, index=x, display_type=Element.DISPLAYTYPE.CONTINUOUS) for x in range(3)]

        # source has 100 rows of data between [0, 100]
        src_data = helpers.create_data(src.layout, length=4)
        src_info = StreamInfo(int(src_data['timestamp'][0]), int(src_data['timestamp'][-1]), len(src_data))
        server.add_stream('/test/source', src, src_info, src_data, [[src_info.start, src_info.end]])
        server.add_stream('/test/source', src, src_info, src_data, [[src_info.start, src_info.end]])

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


def _print_result_on_error(result):
    if result.exit_code == -1:
        print("exception: ", result.exception)
    if result.exit_code != 0:
        print("output: ", result.output)


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
    ts = src_data['timestamp']
    intervals = [[ts[0], ts[24]],
                 [ts[25], ts[49]],
                 [ts[50], ts[74]],
                 [ts[75], ts[99]]]
    src_info = StreamInfo(int(src_data['timestamp'][0]), int(src_data['timestamp'][-1]), len(src_data))
    server.add_stream('/test/source', src, src_info, pipe_data, intervals)
    return src_data
