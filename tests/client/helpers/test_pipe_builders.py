import asyncio
import numpy as np
import logging
import datetime
from unittest import mock
from icecream import ic
import unittest
from joule.models.pipes import interval_token, EmptyPipe
from joule.models.data_stream import StreamInfo, DataStream
from joule.models.element import Element
from joule import api
from joule.errors import ConfigurationError, ApiError
from joule.client.helpers import build_network_pipes
from joule import errors
from tests import helpers
from tests.cli.fake_joule import FakeJoule, FakeJouleTestCase, MockDbEntry

log = logging.getLogger('aiohttp.access')
log.setLevel(logging.WARNING)


class TestPipeHelpers(FakeJouleTestCase):

    def test_reads_historic_data(self):
        server = FakeJoule()
        src_data = create_source_data(server)

        self.start_server(server)
        ''
        my_node = api.get_node()

        async def runner():
            pipes_in, pipes_out = await build_network_pipes({'input': '/test/source:uint8[x,y,z]'},
                                                            {},
                                                            {},
                                                            my_node,
                                                            0, 100,
                                                            force=True)
            blk1 = await pipes_in['input'].read()
            self.assertTrue(pipes_in['input'].end_of_interval)
            pipes_in['input'].consume(len(blk1))
            blk2 = await pipes_in['input'].read()
            pipes_in['input'].consume(len(blk2))
            rx_data = np.hstack((blk1,
                                 interval_token(pipes_in['input'].layout),
                                 blk2))
            np.testing.assert_array_equal(rx_data, src_data)
            with self.assertRaises(EmptyPipe):
                await pipes_in['input'].read()
            await my_node.close()

        with self.assertLogs(level='INFO') as log:
            asyncio.run(runner())
        log_dump = ' '.join(log.output)
        self.stop_server()
        

    def test_builds_live_input_pipes(self):
        server = FakeJoule()
        src_data = create_source_data(server, is_destination=True)

        self.start_server(server)
        loop = asyncio.new_event_loop()
        my_node = api.get_node()

        async def runner():
            pipes_in, pipes_out = await build_network_pipes({'input': '/test/source:uint8[x,y,z]'},
                                                            {},
                                                            {},
                                                            my_node,
                                                            None, None, True)
            blk1 = await pipes_in['input'].read()
            self.assertTrue(pipes_in['input'].end_of_interval)
            pipes_in['input'].consume(len(blk1))
            blk2 = await pipes_in['input'].read()
            pipes_in['input'].consume(len(blk2))
            rx_data = np.hstack((blk1,
                                 interval_token(pipes_in['input'].layout),
                                 blk2))
            np.testing.assert_array_equal(rx_data, src_data)
            with self.assertRaises(EmptyPipe):
                await pipes_in['input'].read()
            await my_node.close()

        with self.assertLogs(level='INFO') as log:
            loop.run_until_complete(runner())
        log_dump = ' '.join(log.output)
        self.stop_server()
        loop.close()

    def test_builds_output_pipes(self):
        server = FakeJoule()
        blk1 = helpers.create_data("uint8_3", start=10, step=1, length=10)
        blk2 = helpers.create_data("uint8_3", start=200, step=1, length=10)

        create_destination(server)

        self.start_server(server)
        my_node = api.get_node()
        async def runner():
            pipes_in, pipes_out = await build_network_pipes({},
                                                            {'output': '/test/dest:uint8[e0,e1,e2]'},
                                                            {},
                                                            my_node,
                                                            10, 210, force=True)
            await pipes_out['output'].write(blk1)
            await pipes_out['output'].close_interval()
            await pipes_out['output'].write(blk2)
            await pipes_out['output'].close_interval()
            await pipes_out['output'].close()
            await my_node.close()

        asyncio.run(runner())
        # first msg should be the data removal
        (stream_id, start, end) = self.msgs.get()
        self.assertEqual(int(stream_id), 8)
        self.assertEqual(int(start), 10)
        self.assertEqual(int(end), 210)
        # next message should be the output data
        mock_entry: MockDbEntry = self.msgs.get()
        np.testing.assert_array_equal(mock_entry.data[:len(blk1)], blk1)
        np.testing.assert_array_equal(mock_entry.data[len(blk1):], blk2)

        self.assertEqual(mock_entry.intervals, [[10, 19], [200, 209]])

        self.stop_server()

    def test_warns_before_data_removal(self):
        server = FakeJoule()
        create_destination(server)

        self.start_server(server)
        ''

        my_node = api.get_node()

        async def runner():
            with mock.patch('joule.client.helpers.pipes.click') as mock_click:
                mock_click.confirm = mock.Mock(return_value=False)
                with self.assertRaises(SystemExit):
                    await build_network_pipes({},
                                              {'output': '/test/dest:uint8[e0,e1,e2]'},
                                              {},
                                              my_node,
                                              1472500708000000, 1476475108000000,
                                              force=False)
                msg = mock_click.confirm.call_args[0][0]
                # check for start time
                self.assertIn("29 Aug", msg)
                # check for end time
                self.assertIn("14 Oct", msg)

                # if end_time not specified anything *after* start is removed
                mock_click.confirm = mock.Mock(return_value=False)
                with self.assertRaises(SystemExit):
                    await build_network_pipes({},
                                              {'output': '/test/dest:uint8[e0,e1,e2]'},
                                              {},
                                              my_node,
                                              1472500708000000, None,
                                              force=False)
                msg = mock_click.confirm.call_args[0][0]
                # check for start time
                self.assertIn("29 Aug", msg)
                # check for *after*
                self.assertIn("after", msg)

                # if start_time not specified anything *before* end is removed
                mock_click.confirm = mock.Mock(return_value=False)
                with self.assertRaises(SystemExit):
                    await build_network_pipes({},
                                              {'output': '/test/dest:uint8[e0,e1,e2]'},
                                              {},
                                              my_node,
                                              None, 1476475108000000,
                                              force=False)
                msg = mock_click.confirm.call_args[0][0]
                # check for *before*
                self.assertIn("before", msg)
                # check for end time
                self.assertIn("14 Oct", msg)
                await my_node.close()

        # suppress "cancelled" notifications when program exits
        #with self.assertLogs(level='INFO'):
        asyncio.run(runner())
        self.stop_server()
        

    def test_creates_output_stream_if_necessary(self):
        server = FakeJoule()
        self.start_server(server)
        ''

        my_node = api.get_node()

        self.assertEqual(len(server.streams), 0)

        async def runner():
            # the destination does not exist
            with self.assertRaises(errors.ApiError):
                await my_node.data_stream_get("/test/dest")
            pipes_in, pipes_out = await build_network_pipes({},
                                                            {'output': '/test/dest:uint8[e0,e1,e2]'},
                                                            {},
                                                            my_node,
                                                            None, None)
            await pipes_out['output'].close()
            # make sure the stream exists
            dest_stream = await my_node.data_stream_get("/test/dest")
            self.assertIsNotNone(dest_stream)

            await my_node.close()

        with self.assertLogs(level='INFO') as log:
            asyncio.run(runner())
        log_dump = ' '.join(log.output)
        self.assertIn('creating', log_dump)
        self.stop_server()
        

    def test_configuration_errors(self):
        server = FakeJoule()
        ''
        self.start_server(server)
        my_node = api.get_node()

        # must specify an inline configuration
        with self.assertRaises(ConfigurationError):
            asyncio.run(build_network_pipes({'input': '/test/source'},
                                                        {},
                                                        {},
                                                        my_node,
                                                        10, 20,
                                                        force=True))
        asyncio.run(my_node.close())
        self.stop_server()
        

    def test_input_errors(self):
        server = FakeJoule()
        create_source_data(server, is_destination=False)
        self.start_server(server)
        loop = asyncio.new_event_loop()
        my_node = api.get_node()

        # errors on layout differences
        with self.assertRaises(ConfigurationError) as e:
            with self.assertLogs(level='INFO'):
                loop.run_until_complete(build_network_pipes({'input': '/test/source:uint8[x,y]'},
                                                            {},
                                                            {},
                                                            my_node,
                                                            10, 20, force=True))
        self.assertIn('uint8_3', str(e.exception))

        # errors if live stream is requested but unavailable
        with self.assertRaises(ApiError) as e:
            loop.run_until_complete(build_network_pipes({'input': '/test/source:uint8[x,y,z]'},
                                                        {},
                                                        {},
                                                        my_node, None, None))
        self.assertIn('not being produced', str(e.exception))
        loop.run_until_complete(my_node.close())
        self.stop_server()
        loop.close()

    def test_output_errors(self):
        server = FakeJoule()
        create_destination(server)
        create_source_data(server, is_destination=True)
        self.start_server(server)
        loop = asyncio.new_event_loop()
        my_node = api.get_node()

        # errors on layout differences
        with self.assertRaises(ConfigurationError) as e:
            loop.run_until_complete(build_network_pipes({},
                                                        {'output': '/test/dest:float32[x,y,z]'},
                                                        {},
                                                        my_node, None, None))
        self.assertIn('uint8_3', str(e.exception))

        # errors if the stream is already being produced
        with self.assertRaises(ApiError) as e:
            loop.run_until_complete(build_network_pipes({},
                                                        {'output': '/test/source:uint8[e0,e1,e2]'},
                                                        {},
                                                        my_node, None, None))
        loop.run_until_complete(my_node.close())
        self.assertIn('already being produced', str(e.exception))
        self.stop_server()
        loop.close()


def create_destination(server):
    # create an empty destination stream
    dest = DataStream(id=8, name="dest", keep_us=100,
                      datatype=DataStream.DATATYPE.UINT8,
                      updated_at=datetime.datetime.utcnow())
    dest.elements = [Element(name="e%d" % x, index=x, display_type=Element.DISPLAYTYPE.CONTINUOUS) for x in range(3)]

    # destination has no data
    server.add_stream('/test/dest', dest, StreamInfo(None, None, 0), None)


def create_source_data(server, is_destination=False):
    # create the source stream
    src = DataStream(id=0, name="source", keep_us=100,
                     datatype=DataStream.DATATYPE.UINT8,
                     is_destination=is_destination,
                      updated_at=datetime.datetime.utcnow())
    src.elements = [Element(name="e%d" % x, index=x, display_type=Element.DISPLAYTYPE.CONTINUOUS) for x in range(3)]

    # source has 100 rows of data
    src_data = np.hstack((helpers.create_data(src.layout),
                          interval_token(src.layout),
                          helpers.create_data(src.layout)))
    src_info = StreamInfo(int(src_data['timestamp'][0]), int(src_data['timestamp'][-1]), len(src_data))
    server.add_stream('/test/source', src, src_info, src_data, [src_info.start, src_info.end])
    return src_data
