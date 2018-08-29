import asyncio
import numpy as np
import requests
import io
from unittest import mock
from contextlib import redirect_stdout

from joule.utilities.pipe_builders import build_network_pipes
from joule.models import Stream, Element, StreamInfo, pipes
from joule.errors import ConfigurationError

from tests import helpers
from tests.cmds.fake_joule import FakeJoule, FakeJouleTestCase, MockDbEntry


class TestPipeHelpers(FakeJouleTestCase):

    def test_builds_historic_input_pipes(self):
        server = FakeJoule()
        src_data = create_source_data(server)

        url = self.start_server(server)
        loop = asyncio.get_event_loop()

        async def runner():
            pipes_in, pipes_out = await build_network_pipes({'input': '/test/source:uint8[x,y,z]'},
                                                            {},
                                                            url,
                                                            0, 100, loop, force=True)
            blk1 = await pipes_in['input'].read()
            self.assertTrue(pipes_in['input'].end_of_interval)
            pipes_in['input'].consume(len(blk1))
            blk2 = await pipes_in['input'].read()
            pipes_in['input'].consume(len(blk2))
            rx_data = np.hstack((blk1,
                                 pipes.interval_token(pipes_in['input'].layout),
                                 blk2))
            np.testing.assert_array_equal(rx_data, src_data)
            with self.assertRaises(pipes.EmptyPipe):
                await pipes_in['input'].read()

        with self.assertLogs(level='INFO') as log:
            loop.run_until_complete(runner())
        log_dump = ' '.join(log.output)
        self.assertIn("historic connection", log_dump)
        self.stop_server()

    def test_builds_live_input_pipes(self):
        server = FakeJoule()
        src_data = create_source_data(server, is_destination=True)

        url = self.start_server(server)
        loop = asyncio.get_event_loop()

        async def runner():
            pipes_in, pipes_out = await build_network_pipes({'input': '/test/source:uint8[x,y,z]'},
                                                            {},
                                                            url,
                                                            None, None, loop)
            blk1 = await pipes_in['input'].read()
            self.assertTrue(pipes_in['input'].end_of_interval)
            pipes_in['input'].consume(len(blk1))
            blk2 = await pipes_in['input'].read()
            pipes_in['input'].consume(len(blk2))
            rx_data = np.hstack((blk1,
                                 pipes.interval_token(pipes_in['input'].layout),
                                 blk2))
            np.testing.assert_array_equal(rx_data, src_data)
            with self.assertRaises(pipes.EmptyPipe):
                await pipes_in['input'].read()

        with self.assertLogs(level='INFO') as log:
            loop.run_until_complete(runner())
        log_dump = ' '.join(log.output)
        self.assertIn("live connection", log_dump)
        self.stop_server()

    def test_builds_output_pipes(self):
        server = FakeJoule()
        blk1 = helpers.create_data("uint8_3", start=10, step=1, length=10)
        blk2 = helpers.create_data("uint8_3", start=200, step=1, length=10)

        create_destination(server)

        url = self.start_server(server)
        loop = asyncio.get_event_loop()

        async def runner():
            pipes_in, pipes_out = await build_network_pipes({},
                                                            {'output': '/test/dest:uint8[e0,e1,e2]'},
                                                            url,
                                                            10, 100, loop, force=True)
            await pipes_out['output'].write(blk1)
            await pipes_out['output'].close_interval()
            await pipes_out['output'].write(blk2)
            await pipes_out['output'].close_interval()
            await pipes_out['output'].close()

        loop.run_until_complete(runner())
        # first msg should be the data removal
        (stream_id, start, end) = self.msgs.get()
        self.assertEqual(int(stream_id), 8)
        self.assertEqual(int(start), 10)
        self.assertEqual(int(end), 100)
        # next message should be the output data
        mock_entry: MockDbEntry = self.msgs.get()
        np.testing.assert_array_equal(mock_entry.data[:len(blk1)], blk1)
        np.testing.assert_array_equal(mock_entry.data[len(blk1):], blk2)
        self.assertEqual(mock_entry.intervals, [[10, 19], [200, 209]])

        self.stop_server()

    def test_warns_before_data_removal(self):
        server = FakeJoule()
        create_destination(server)

        url = self.start_server(server)
        loop = asyncio.get_event_loop()

        async def runner():
            with mock.patch('joule.utilities.pipe_builders.click') as mock_click:
                mock_click.confirm = mock.Mock(return_value=False)
                with self.assertRaises(SystemExit):
                    await build_network_pipes({},
                                              {'output': '/test/dest:uint8[e0,e1,e2]'},
                                              url,
                                              1472500708000000, 1476475108000000,
                                              loop, force=False)
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
                                              url,
                                              1472500708000000, None,
                                              loop, force=False)
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
                                              url,
                                              None, 1476475108000000,
                                              loop, force=False)
                msg = mock_click.confirm.call_args[0][0]
                # check for *before*
                self.assertIn("before", msg)
                # check for end time
                self.assertIn("14 Oct", msg)

        # suppress "cancelled" notifications when program exits
        with self.assertLogs(level='INFO'):
            loop.run_until_complete(runner())
        self.stop_server()

    def test_creates_output_stream_if_necessary(self):
        server = FakeJoule()
        url = self.start_server(server)
        loop = asyncio.get_event_loop()

        self.assertEqual(len(server.streams), 0)

        async def runner():
            # the destination does not exist
            resp = requests.get(url + '/stream.json?path=/test/dest')
            self.assertEqual(resp.status_code, 404)
            pipes_in, pipes_out = await build_network_pipes({},
                                                            {'output': '/test/dest:uint8[e0,e1,e2]'},
                                                            url,
                                                            None, None, loop)
            await pipes_out['output'].close()
            # make sure the stream exists
            resp = requests.get(url + '/stream.json?path=/test/dest')
            self.assertEqual(resp.status_code, 200)

        with self.assertLogs(level='INFO') as log:
            loop.run_until_complete(runner())
        log_dump = ' '.join(log.output)
        self.assertIn('creating', log_dump)
        self.stop_server()

    def test_configuration_errors(self):
        loop = asyncio.get_event_loop()

        # must specify an inline configuration
        with self.assertRaises(ConfigurationError) as e:
            with self.assertLogs(level='INFO') as log:
                loop.run_until_complete(build_network_pipes({'input': '/test/source'},
                                                            {}, 'empty', 10, 20, loop, force=True))
            log_dump = ' '.join(log.output)
            self.assertIn('inline', log_dump)

    def test_input_errors(self):
        server = FakeJoule()
        create_source_data(server, is_destination=False)
        url = self.start_server(server)
        loop = asyncio.get_event_loop()

        # errors on layout differences
        with self.assertRaises(ConfigurationError) as e:
            with self.assertLogs(level='INFO'):
                loop.run_until_complete(build_network_pipes({'input': '/test/source:uint8[x,y]'},
                                                            {}, url, 10, 20, loop, force=True))
        self.assertIn('uint8_3', str(e.exception))

        # errors if live stream is requested but unavailable
        with self.assertRaises(ConfigurationError) as e:
            loop.run_until_complete(build_network_pipes({'input': '/test/source:uint8[x,y,z]'},
                                                        {}, url, None, None, loop))
        self.assertIn('not being produced', str(e.exception))
        self.stop_server()

    def test_output_errors(self):
        server = FakeJoule()
        create_destination(server)
        create_source_data(server, is_destination=True)
        url = self.start_server(server)
        loop = asyncio.get_event_loop()

        # errors on layout differences
        with self.assertRaises(ConfigurationError) as e:
            loop.run_until_complete(build_network_pipes({},
                                                        {'output': '/test/dest:float32[x,y,z]'},
                                                        url, None, None, loop))
        self.assertIn('uint8_3', str(e.exception))

        # errors if the stream is already being produced
        with self.assertRaises(ConfigurationError) as e:
            loop.run_until_complete(build_network_pipes({},
                                                        {'output': '/test/source:uint8[e0,e1,e2]'},
                                                        url, None, None, loop))
        self.assertIn('already being produced', str(e.exception))
        self.stop_server()


def create_destination(server):
    # create an empty destination stream
    dest = Stream(id=8, name="dest", keep_us=100, datatype=Stream.DATATYPE.UINT8)
    dest.elements = [Element(name="e%d" % x, index=x, display_type=Element.DISPLAYTYPE.CONTINUOUS) for x in range(3)]

    # destination has no data
    server.add_stream('/test/dest', dest, StreamInfo(None, None, 0), None)


def create_source_data(server, is_destination=False):
    # create the source stream
    src = Stream(id=0, name="source", keep_us=100, datatype=Stream.DATATYPE.UINT8,
                 is_destination=is_destination)
    src.elements = [Element(name="e%d" % x, index=x, display_type=Element.DISPLAYTYPE.CONTINUOUS) for x in range(3)]

    # source has 100 rows of data
    src_data = np.hstack((helpers.create_data(src.layout),
                          pipes.interval_token(src.layout),
                          helpers.create_data(src.layout)))
    src_info = StreamInfo(int(src_data['timestamp'][0]), int(src_data['timestamp'][-1]), len(src_data))
    server.add_stream('/test/source', src, src_info, src_data, [src_info.start, src_info.end])
    return src_data
