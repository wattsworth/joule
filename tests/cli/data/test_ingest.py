from click.testing import CliRunner

import warnings
import numpy as np
import logging
import tempfile
import h5py
import json
import datetime
import unittest
from icecream import ic
from ..fake_joule import FakeJoule, FakeJouleTestCase
from joule.cli import main
from joule.models import DataStream, Element, StreamInfo
from joule.api.data_stream import Element as ApiElement
from tests import helpers

warnings.simplefilter('always')
log = logging.getLogger('aiohttp.access')
log.setLevel(logging.WARNING)


class TestDataIngest(FakeJouleTestCase):

    def test_ingests_data_to_empty_existing_stream(self):
        server = FakeJoule()
        # create the source stream
        src = DataStream(id=0, name="existing", keep_us=100,
                         datatype=DataStream.DATATYPE.FLOAT32, updated_at=datetime.datetime.utcnow())
        src.elements = [Element(name="e%d" % x, index=x, display_type=Element.DISPLAYTYPE.CONTINUOUS) for x in range(3)]
        src_data = helpers.create_data(src.layout, length=22000)
        src_info = StreamInfo(0, 0, 0, 0)
        server.add_stream('/test/existing', src, src_info, None)
        self.start_server(server)
        runner = CliRunner()
        with tempfile.NamedTemporaryFile() as data_file:
            write_hd5_data(data_file, src_data)
            result = runner.invoke(main, ['data', 'ingest', '--file', data_file.name, '--stream', '/test/existing'])
            _print_result_on_error(result)
            self.assertEqual(result.exit_code, 0)
        db_obj = self.msgs.get()
        np.testing.assert_array_equal(src_data, db_obj.data)
        # uses the stream parameter instead of the hd5 attrs
        self.assertEqual(db_obj.stream.name, 'existing')
        self.stop_server()

    def test_datatype_mismatch(self):
        #  the datatype of the file and target stream must match
        server = FakeJoule()
        # create the source stream
        src = DataStream(id=0, name="dest", keep_us=100,
                         datatype=DataStream.DATATYPE.UINT16, updated_at=datetime.datetime.utcnow())
        src.elements = [Element(name="e%d" % x, index=x, display_type=Element.DISPLAYTYPE.CONTINUOUS) for x in range(3)]
        # source has 100 rows of data between [0, 100]
        file_data = helpers.create_data('int16_3')
        src_info = StreamInfo(0, 0, 0, 0)
        server.add_stream('/test/dest', src, src_info, None)
        self.start_server(server)
        runner = CliRunner()
        with tempfile.NamedTemporaryFile() as data_file:
            write_hd5_data(data_file, file_data)
            result = runner.invoke(main, ['data', 'ingest', '--file', data_file.name])
            self.assertIn("datatype", result.output)
            self.assertNotEqual(result.exit_code, 0)

        self.stop_server()

    def test_confirms_data_removal(self):
        # if there is existing data in the target, confirm removal
        server = FakeJoule()
        # create the source stream
        src = DataStream(id=0, name="dest", keep_us=100,
                         datatype=DataStream.DATATYPE.FLOAT32, updated_at=datetime.datetime.utcnow())
        src.elements = [Element(name="e%d" % x, index=x, display_type=Element.DISPLAYTYPE.CONTINUOUS) for x in range(3)]
        # source has 100 rows of data between [0, 100]
        src_data = helpers.create_data(src.layout, length=1000)
        # File:    |----|
        # DataStream:     |-----|
        src_info = StreamInfo(int(src_data['timestamp'][500]),
                              int(src_data['timestamp'][-1]),
                              500)
        server.add_stream('/test/dest', src, src_info, src_data[500:])
        self.start_server(server)
        runner = CliRunner()
        with tempfile.NamedTemporaryFile() as data_file:
            write_hd5_data(data_file, src_data[:750])
            result = runner.invoke(main, ['data', 'ingest', '--file', data_file.name],
                                   input='N')
            _print_result_on_error(result)
            self.assertEqual(result.exit_code, 0)
            self.assertIn('Cancelled', result.output)

        self.stop_server()

    def test_dataset_mismatch(self):
        # the length of [data] and [timestamp]  must match
        runner = CliRunner()
        with tempfile.NamedTemporaryFile() as data_file:
            with h5py.File(data_file.name, 'w') as hdf_root:
                hdf_root.create_dataset('data', (10, 10),
                                        dtype=np.dtype('float32'),
                                        compression='gzip')
                hdf_root.create_dataset('timestamp', (11, 1),
                                        dtype=np.dtype('float32'),
                                        compression='gzip')
            result = runner.invoke(main, ['data', 'ingest', '--file', data_file.name])
            self.assertIn("Error", result.output)
            self.assertNotEqual(result.exit_code, 0)

    def test_stream_element_mismatch(self):
        #  the datatype of the file and target stream must match
        server = FakeJoule()
        # create the source stream
        src = DataStream(id=0, name="dest", keep_us=100,
                         datatype=DataStream.DATATYPE.UINT16, updated_at=datetime.datetime.utcnow())
        src.elements = [Element(name="e%d" % x, index=x, display_type=Element.DISPLAYTYPE.CONTINUOUS) for x in range(4)]
        # source has 100 rows of data between [0, 100]
        file_data = helpers.create_data('uint16_3')
        src_info = StreamInfo(0, 0, 0, 0)
        server.add_stream('/test/dest', src, src_info, None)
        self.start_server(server)
        runner = CliRunner()
        with tempfile.NamedTemporaryFile() as data_file:
            write_hd5_data(data_file, file_data)
            result = runner.invoke(main, ['data', 'ingest', '--file', data_file.name])
            self.assertIn("elements", result.output)
            self.assertNotEqual(result.exit_code, 0)

        self.stop_server()

    def test_creates_stream_from_attributes(self):
        # creates the target stream based on hdf attrs
        server = FakeJoule()
        src_data = helpers.create_data('float32_3')
        self.start_server(server)
        runner = CliRunner()

        with tempfile.NamedTemporaryFile() as data_file:
            write_hd5_data(data_file, src_data[:750])
            result = runner.invoke(main, ['data', 'ingest', '--file', data_file.name],
                                   input='N')
            _print_result_on_error(result)
            self.assertEqual(result.exit_code, 0)
            # prints a message about the new stream
            self.assertIn('/test/dest', result.output)
        db_entry = self.msgs.get()
        # make sure all the elements are present
        elem_names = [e.name for e in db_entry.stream.elements]
        expected_names = ['Test %d' % i for i in range(3)]
        self.assertEqual(elem_names, expected_names)
        self.assertEqual(db_entry.stream.name, 'dest')
        self.stop_server()

    def test_invalid_data_structure(self):
        runner = CliRunner()
        with tempfile.NamedTemporaryFile() as data_file:
            with h5py.File(data_file.name, 'w') as hdf_root:
                hdf_root.create_dataset('data', (1, 10),
                                        dtype=np.dtype('float32'),
                                        compression='gzip')

            result = runner.invoke(main, ['data', 'ingest', '--file', data_file.name])
            self.assertIn("Error", result.output)
            self.assertNotEqual(result.exit_code, 0)

    def test_invalid_filetype(self):
        runner = CliRunner()
        with tempfile.NamedTemporaryFile() as bad_file:
            with open(bad_file.name, 'w') as f:
                f.write('invalid filetype')
            result = runner.invoke(main, ['data', 'ingest', '--file', bad_file.name])
            self.assertIn("Error", result.output)
            self.assertNotEqual(result.exit_code, 0)


def write_hd5_data(path, data):
    with h5py.File(path, 'w') as hdf_root:
        hdf_data = hdf_root.create_dataset('data', data['data'].shape,
                                           dtype=data.dtype[1].base,
                                           compression='gzip')
        hdf_timestamps = hdf_root.create_dataset('timestamp', [len(data), 1],
                                                 dtype='i8',
                                                 compression='gzip')
        hdf_data[...] = data['data']
        hdf_timestamps[...] = data['timestamp'][:, None]
        hdf_root.attrs['path'] = '/test/dest'
        elements = [ApiElement(name='Test %d' % i,
                               display_type='discrete') for i in range(data['data'].shape[1])]
        element_json = json.dumps([e.to_json() for e in elements])
        hdf_root.attrs['element_json'] = element_json


def _print_result_on_error(result):
    if result.exit_code != 0:
        print("output: ", result.output)
        print("exception: ", result.exception)
