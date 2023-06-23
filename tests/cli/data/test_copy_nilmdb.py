from click.testing import CliRunner
from aiohttp.test_utils import unused_port
import warnings
import asyncio
import numpy as np
import multiprocessing
import time
import os
import signal
import json
import psutil
import datetime
import unittest

from ..fake_joule import FakeJoule, FakeJouleTestCase
from tests.models.data_store.fake_nilmdb import FakeNilmdb, FakeStream
from joule.cli import main
from joule.models import DataStream, Element, StreamInfo
from tests import helpers

warnings.simplefilter('always')


class TestDataCopyWithNilmDb(FakeJouleTestCase):

    def _start_nilmdb(self, msgs):
        port = unused_port()
        self.nilmdb_proc = multiprocessing.Process(target=self._run_nilmdb, args=(port, msgs))
        self.nilmdb_proc.start()
        ready = False
        time.sleep(0.01)

        while not ready:
            for conn in psutil.net_connections():
                if conn.laddr.port == port:
                    ready = True
                    break
            else:
                time.sleep(0.01)
        return "http://127.0.0.1:%d" % port

    def _stop_nilmdb(self):
        if self.nilmdb_proc is None:
            return
        # aiohttp doesn't always quit with SIGTERM
        os.kill(self.nilmdb_proc.pid, signal.SIGKILL)
        # join any zombies
        self.nilmdb_proc.join()
        del self.nilmdb_proc

    def _run_nilmdb(self, port, msgs):

        loop = asyncio.new_event_loop()
        server = FakeNilmdb()
        # create an empty stream
        server.streams['/existing/float32_3'] = FakeStream(
            layout='float32_3', start=0, end=0, rows=0)
        # create a source stream
        server.streams['/test/source'] = FakeStream(
            layout='float32_3', start=0, end=100, rows=1000)

        self.nilmdb_task = loop.create_task(server.start(port, msgs))
        loop.run_forever()

    def test_copies_data_to_nilmdb(self):

        source_server = FakeJoule()
        nilmdb_msgs = multiprocessing.Queue()
        dest_url = self._start_nilmdb(nilmdb_msgs)
        # create the source and destination streams
        src_data = create_source_data(source_server)  # helpers.create_data(src.layout)

        src_stream = DataStream(id=1, name="dest", keep_us=100,
                                datatype=DataStream.DATATYPE.FLOAT32, updated_at=datetime.datetime.utcnow())
        src_stream.elements = [Element(name="e%d" % x, index=x, display_type=Element.DISPLAYTYPE.CONTINUOUS) for x in
                               range(3)]
        source_server.add_stream('/test/destination', src_stream, StreamInfo(None, None, 0), None)

        self.start_server(source_server)
        runner = CliRunner()
        result = runner.invoke(main, ['data', 'copy',
                                      '-d', dest_url, '/test/source', '/existing/float32_3'],
                               input='y\n', catch_exceptions=True)
        _print_result_on_error(result)
        # expect data transfer call
        nilmdb_call = nilmdb_msgs.get()
        self.assertEqual('stream_insert', nilmdb_call['action'])
        data = nilmdb_call['data']
        np.testing.assert_array_equal(src_data, data)
        self.assertEqual(0, result.exit_code)
        self._stop_nilmdb()
        self.stop_server()
        del nilmdb_msgs

    def test_creates_nilmdb_stream_if_necessary(self):
        source_server = FakeJoule()
        nilmdb_msgs = multiprocessing.Queue()
        dest_url = self._start_nilmdb(nilmdb_msgs)
        # create just the source stream
        src_data = create_source_data(source_server)  # helpers.create_data(src.layout)

        src_stream = DataStream(id=1, name="dest", keep_us=100,
                                datatype=DataStream.DATATYPE.FLOAT32, updated_at=datetime.datetime.utcnow())
        src_stream.elements = [Element(name="e%d" % x, index=x, display_type=Element.DISPLAYTYPE.CONTINUOUS) for x in
                               range(3)]
        source_server.add_stream('/test/destination', src_stream, StreamInfo(None, None, 0), None)

        self.start_server(source_server)
        runner = CliRunner()
        result = runner.invoke(main, ['data', 'copy',
                                      '-d', dest_url, '/test/source', '/test/destination'], catch_exceptions=False)
        _print_result_on_error(result)
        # expect a stream create call
        nilmdb_call = nilmdb_msgs.get()
        self.assertEqual('stream_create', nilmdb_call['action'])
        self.assertEqual({'path': '/test/destination', 'layout': 'float32_3'}, nilmdb_call['params'])
        # expect a metadata call
        nilmdb_call = nilmdb_msgs.get()
        self.assertEqual('set_metadata', nilmdb_call['action'])
        self.assertEqual('/test/destination', nilmdb_call['params']['path'])
        self.assertEqual('config_key__', list(json.loads(nilmdb_call['params']['data']).keys())[0])
        # expect data transfer call
        nilmdb_call = nilmdb_msgs.get()
        self.assertEqual('stream_insert', nilmdb_call['action'])
        data = nilmdb_call['data']
        np.testing.assert_array_equal(src_data, data)
        self.assertEqual(0, result.exit_code)
        self._stop_nilmdb()
        self.stop_server()
        del nilmdb_msgs

    def test_copies_data_from_nilmdb(self):
        dest_server = FakeJoule()
        nilmdb_msgs = multiprocessing.Queue()
        source_url = self._start_nilmdb(nilmdb_msgs)
        # create the source and destination streams

        self.start_server(dest_server)
        runner = CliRunner()
        result = runner.invoke(main, ['data', 'copy',
                                      '--source-url', source_url,
                                      '-d', "fake_joule", '/test/source', '/test/destination'],
                               catch_exceptions=False)
        _print_result_on_error(result)
        self.assertEqual(0, result.exit_code)
        mock_entry = self.msgs.get()
        self.assertEqual(len(mock_entry.data), 1000)
        self._stop_nilmdb()
        self.stop_server()
        del nilmdb_msgs


def _print_result_on_error(result):
    if result.exit_code == -1:
        print("exception: ", result.exception)
    if result.exit_code != 0:
        print("output: ", result.output)


def create_source_data(server):
    # create the source stream
    src = DataStream(id=0, name="source", keep_us=100,
                     datatype=DataStream.DATATYPE.FLOAT32, updated_at=datetime.datetime.utcnow())
    src.elements = [Element(name="e%d" % x, index=x, display_type=Element.DISPLAYTYPE.CONTINUOUS) for x in range(3)]

    # source has 100 rows of data
    src_data = helpers.create_data(src.layout, length=100, start=0, step=1)
    ts = src_data['timestamp']
    intervals = [[ts[0], ts[99]]]
    src_info = StreamInfo(int(src_data['timestamp'][0]), int(src_data['timestamp'][-1]),
                          len(src_data))
    server.add_stream('/test/source', src, src_info, src_data, intervals)
    return src_data
