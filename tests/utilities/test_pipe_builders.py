import asyncio
import numpy as np
import requests
import io
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

        f = io.StringIO()
        with redirect_stdout(f):
            loop.run_until_complete(runner())
        self.assertIn("historic connection", f.getvalue())
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

        f = io.StringIO()
        with redirect_stdout(f):
            loop.run_until_complete(runner())
        self.assertIn("live connection", f.getvalue())
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
                                                            None, None, loop)
            await pipes_out['output'].write(blk1)
            await pipes_out['output'].close_interval()
            await pipes_out['output'].write(blk2)
            await pipes_out['output'].close_interval()
            await pipes_out['output'].close()

        loop.run_until_complete(runner())
        mock_entry: MockDbEntry = self.msgs.get()
        np.testing.assert_array_equal(mock_entry.data[:len(blk1)], blk1)
        np.testing.assert_array_equal(mock_entry.data[len(blk1):], blk2)
        self.assertEqual(mock_entry.intervals, [[10, 19], [200, 209]])

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

        f = io.StringIO()
        with redirect_stdout(f):
            loop.run_until_complete(runner())
        self.assertIn('creating', f.getvalue())
        self.stop_server()

    def test_configuration_errors(self):
        loop = asyncio.get_event_loop()

        # must specify an inline configuration
        with self.assertRaises(ConfigurationError) as e:
            f = io.StringIO()
            with redirect_stdout(f):
                loop.run_until_complete(build_network_pipes({'input': '/test/source'},
                                                            {}, 'empty', 10, 20, loop, force=True))
        self.assertIn('inline', str(e.exception))

    def test_input_errors(self):
        server = FakeJoule()
        create_source_data(server, is_destination=False)
        url = self.start_server(server)
        loop = asyncio.get_event_loop()

        # errors on layout differences
        with self.assertRaises(ConfigurationError) as e:
            f = io.StringIO()
            with redirect_stdout(f):
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
    dest = Stream(id=0, name="dest", keep_us=100, datatype=Stream.DATATYPE.UINT8)
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
