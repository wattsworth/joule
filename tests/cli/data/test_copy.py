from click.testing import CliRunner
import warnings
import numpy as np
import logging
import datetime
import asyncio
import unittest

from ..fake_joule import FakeJoule, FakeJouleTestCase, MockDbEntry
from joule.cli import main
from joule.models import DataStream, Element, StreamInfo, pipes
from tests import helpers
import time

warnings.simplefilter('always')
log = logging.getLogger('aiohttp.access')
log.setLevel(logging.WARNING)


class TestDataCopy(FakeJouleTestCase):

    def test_copies_all_data(self):
        server = FakeJoule()
        # create the source and destination streams
        src_data = create_source_data(server, break_into_intervals=False)  # helpers.create_data(src.layout)
        # dest is empty
        dest = DataStream(id=1, name="dest", keep_us=100,
                          datatype=DataStream.DATATYPE.FLOAT32, updated_at=datetime.datetime.utcnow())
        dest.elements = [Element(name="e%d" % x, index=x, display_type=Element.DISPLAYTYPE.CONTINUOUS) for x in
                         range(3)]
        server.add_stream('/test/destination', dest, StreamInfo(None, None, 0), None)

        self.start_server(server)
        runner = CliRunner()
        result = runner.invoke(main, ['data', 'copy', '/test/source', '/test/destination'])
        _print_result_on_error(result)
        self.assertEqual(result.exit_code, 0)
        # wait for the copy to complete
        while self.msgs.empty():
            time.sleep(0.1)
        max_msgs = 40
        num_msgs = 0
        mock_entry = MockDbEntry(None,None,np.array([]))
        while num_msgs<max_msgs:
            num_msgs+=1
            msg = self.msgs.get()
            if type(msg)==MockDbEntry:
                mock_entry = msg
            if len(mock_entry.data)==len(src_data) and self.msgs.empty():
                break
        #print(self.msgs.get())
        np.testing.assert_array_equal(src_data, mock_entry.data)
        # self.assertEqual(len(mock_entry.intervals), 3)
        self.stop_server()

    @unittest.skip('fakejoule does not handle time bound queries so this test is not useful')
    def test_copies_new_data(self):
        server = FakeJoule()
        # create the source and destination streams
        src_data = create_source_data(server)  # helpers.create_data(src.layout)
        # dest has half the data
        dest = DataStream(id=1, name="dest", keep_us=100,
                          datatype=DataStream.DATATYPE.FLOAT32, updated_at=datetime.datetime.utcnow())
        dest.elements = [Element(name="e%d" % x, index=x, display_type=Element.DISPLAYTYPE.CONTINUOUS) for x in
                         range(3)]
        # destination is missing first interval but this won't be copied with the --new flag
        dest_interval = server.streams['/test/source'].intervals[1]
        dest_data = np.copy(src_data[dest_interval[0]:dest_interval[1]])
        server.add_stream('/test/destination', dest,
                          StreamInfo(int(dest_interval[0]), int(dest_interval[1]), len(dest_data)),
                          dest_data, [dest_interval])
        self.start_server(server)
        runner = CliRunner()
        result = runner.invoke(main, ['data', 'copy', '--new', '/test/source', '/test/destination'])
        print(result.output)
        _print_result_on_error(result)
        self.assertEqual(result.exit_code, 0)
        while self.msgs.empty():
            time.sleep(0.1)
        while not self.msgs.empty():
            msg = self.msgs.get()
            if type(msg) is MockDbEntry:
                print(msg)
        self.stop_server()

    def test_does_not_copy_existing_data(self):
        server = FakeJoule()
        # create the source and destination streams
        src_data = create_source_data(server)  # helpers.create_data(src.layout)
        # dest has the same intervals as source so nothing is copied
        ts = src_data['timestamp']
        intervals = server.streams['/test/source'].intervals

        dest = DataStream(id=1, name="dest", keep_us=100,
                          datatype=DataStream.DATATYPE.FLOAT32, updated_at=datetime.datetime.utcnow())
        dest.elements = [Element(name="e%d" % x, index=x, display_type=Element.DISPLAYTYPE.CONTINUOUS) for x in
                         range(3)]
        server.add_stream('/test/destination', dest, StreamInfo(int(ts[0]), int(ts[-1]),
                                                                len(ts)), src_data, intervals)
        self.start_server(server)
        runner = CliRunner()
        result = runner.invoke(main, ['data', 'copy',
                                      '--start', str(ts[0]), '--end', str(ts[-1]),
                                      '/test/source', '/test/destination'])
        _print_result_on_error(result)
        self.assertEqual(result.exit_code, 0)
        # only the annotations get was called (twice for each interval: src and dest)
        self.assertTrue(self.msgs.qsize(), len(intervals) * 2)
        self.stop_server()

    def test_creates_stream_if_necessary(self):
        server = FakeJoule()
        # create the source stream
        src = DataStream(id=0, name="source", keep_us=100,
                         datatype=DataStream.DATATYPE.FLOAT32,
                         updated_at=datetime.datetime.utcnow())
        src.elements = [Element(name="e%d" % x, index=x, display_type=Element.DISPLAYTYPE.CONTINUOUS) for x in range(3)]

        # source has 100 rows of data between [0, 100]
        src_data = helpers.create_data(src.layout, length=4)
        src_info = StreamInfo(int(src_data['timestamp'][0]), int(src_data['timestamp'][-1]), len(src_data))
        server.add_stream('/test/source', src, src_info, src_data, [[src_info.start, src_info.end]])
        server.add_stream('/test/source', src, src_info, src_data, [[src_info.start, src_info.end]])

        self.start_server(server)
        runner = CliRunner()
        result = runner.invoke(main, ['data', 'copy', '/test/source', '/test/destination'])
        _print_result_on_error(result)
        self.assertEqual(result.exit_code, 0)
        while self.msgs.empty():
            time.sleep(0.1)
            print("waiting...")
        mock_entry = self.msgs.get()
        np.testing.assert_array_equal(src_data, mock_entry.data)
        self.stop_server()

    def test_when_source_is_empty(self):
        server = FakeJoule()
        # source has no data
        src_info = StreamInfo(None, None, 0)
        # create the source stream
        src = DataStream(id=0, name="source", keep_us=100,
                         datatype=DataStream.DATATYPE.FLOAT32, updated_at=datetime.datetime.utcnow())
        src.elements = [Element(name="e%d" % x, index=x, display_type=Element.DISPLAYTYPE.CONTINUOUS) for x in range(3)]
        server.add_stream('/test/source', src, src_info, np.ndarray([]))
        self.start_server(server)
        runner = CliRunner()
        result = runner.invoke(main, ['data', 'copy', '/test/source', '/test/destination'])
        self.assertTrue('Error' in result.output and 'source' in result.output)
        self.assertEqual(result.exit_code, 1)
        self.stop_server()

    def test_when_destination_is_invalid(self):
        server = FakeJoule()
        # create the source stream
        src = DataStream(id=0, name="source", keep_us=100,
                         datatype=DataStream.DATATYPE.FLOAT32, updated_at=datetime.datetime.utcnow())
        src.elements = [Element(name="e%d" % x, index=x, display_type=Element.DISPLAYTYPE.CONTINUOUS) for x in range(3)]

        # source has 100 rows of data between [0, 100]
        src_data = helpers.create_data(src.layout, length=4)
        src_info = StreamInfo(int(src_data['timestamp'][0]), int(src_data['timestamp'][-1]), len(src_data))

        server.add_stream('/test/source', src, src_info, np.ndarray([]))
        self.start_server(server)
        runner = CliRunner()
        result = runner.invoke(main, ['data', 'copy', '/test/source', 'badpath'])
        self.assertTrue('Error' in result.output and 'destination' in result.output)
        self.assertEqual(result.exit_code, 1)
        self.stop_server()

    def test_when_server_returns_invalid_data(self):
        server = FakeJoule()
        create_source_data(server)

        server.response = "notjson"
        server.http_code = 200
        self.start_server(server)
        runner = CliRunner()
        result = runner.invoke(main, ['data', 'copy', '/test/source', '/stub/response'])
        self.assertTrue('Error' in result.output)

        self.assertEqual(result.exit_code, 1)
        self.stop_server()

    def test_incompatible_layouts(self):
        server = FakeJoule()
        create_source_data(server)
        dest = DataStream(id=1, name="dest", keep_us=100,
                          datatype=DataStream.DATATYPE.FLOAT32, updated_at=datetime.datetime.utcnow())
        dest.elements = [Element(name="e%d" % x, index=x, display_type=Element.DISPLAYTYPE.CONTINUOUS) for x in
                         range(5)]
        server.add_stream('/test/destination', dest, StreamInfo(None, None, 0), None)
        self.start_server(server)
        runner = CliRunner()
        result = runner.invoke(main, ['data', 'copy', '/test/source', '/test/destination'])
        self.assertTrue('not compatible' in result.output)
        self.assertEqual(result.exit_code, 1)
        self.stop_server()

    def test_warn_on_different_elements(self):
        server = FakeJoule()
        create_source_data(server)
        dest = DataStream(id=1, name="dest", keep_us=100,
                          datatype=DataStream.DATATYPE.FLOAT32, updated_at=datetime.datetime.utcnow())
        dest.elements = [
            Element(name="different%d" % x, index=x, units='other', display_type=Element.DISPLAYTYPE.CONTINUOUS) for x
            in
            range(3)]
        server.add_stream('/test/destination', dest, StreamInfo(None, None, 0), None)
        self.start_server(server)
        runner = CliRunner()
        # does not copy without confirmation
        runner.invoke(main, ['data', 'copy', '/test/source', '/test/destination'])
        self.assertTrue(self.msgs.empty())
        # copies with confirmation
        result = runner.invoke(main, ['data', 'copy', '/test/source', '/test/destination'],
                               input='y\n')
        mock_entry = self.msgs.get()
        self.assertTrue(len(mock_entry.data) > 0)
        self.assertEqual(result.exit_code, 0)
        self.stop_server()

    def test_start_must_be_before_end(self):
        server = FakeJoule()
        create_source_data(server)
        self.start_server(server)
        runner = CliRunner()
        # does not copy without confirmation
        result = runner.invoke(main, ['data', 'copy',
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
        self.start_server(server)
        runner = CliRunner()
        result = runner.invoke(main, ['data', 'copy',
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
        self.start_server(server)
        runner = CliRunner()
        result = runner.invoke(main, ['data', 'copy',
                                      '/test/source', '/test/destination'])
        self.assertEqual(result.exit_code, 1)
        self.assertTrue('Error' in result.output and 'destination' in result.output)
        self.stop_server()


def _print_result_on_error(result):
    if result.exit_code != 0:
        print("output: ", result.output)
        print("exception: ", result.exception)


def create_source_data(server, break_into_intervals=True):
    # create the source stream
    src = DataStream(id=0, name="source", keep_us=100,
                     datatype=DataStream.DATATYPE.FLOAT32, updated_at=datetime.datetime.utcnow())
    src.elements = [Element(name="e%d" % x, index=x, display_type=Element.DISPLAYTYPE.CONTINUOUS) for x in range(3)]

    # source has 100 rows of data in four intervals between [0, 100]
    src_data = helpers.create_data(src.layout, length=100, start=0, step=1)
    if break_into_intervals:
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
    else:
        pipe_data = src_data
        intervals = [[src_data['timestamp'][0],src_data['timestamp'][-1]]]
    src_info = StreamInfo(int(src_data['timestamp'][0]), int(src_data['timestamp'][-1]), len(src_data))
    server.add_stream('/test/source', src, src_info, pipe_data, intervals)
    return src_data
