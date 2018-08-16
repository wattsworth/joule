import asyncio
import numpy as np
from joule.client.helpers import pipes

from joule.client.helpers.pipes import build_network_pipes
from joule.models import Stream, Element, StreamInfo, pipes

from tests import helpers
from tests.cmds.fake_joule import FakeJoule, FakeJouleTestCase


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
                                                            0, 100, loop)
            data = await pipes_in['input'].read()
            np.testing.assert_array_equal(data, src_data)
            pipes_in['input'].consume(len(data))
            with self.assertRaises(pipes.EmptyPipe):
                await pipes_in['input'].read()
        loop.run_until_complete(runner())
        self.stop_server()

    def test_builds_live_input_pipes(self):
        pass


def create_source_data(server):
    # create the source stream
    src = Stream(id=0, name="source", keep_us=100, datatype=Stream.DATATYPE.UINT8)
    src.elements = [Element(name="e%d" % x, index=x, display_type=Element.DISPLAYTYPE.CONTINUOUS) for x in range(3)]

    # source has 100 rows of data in four intervals between [0, 100]
    src_data = helpers.create_data(src.layout)
    src_info = StreamInfo(int(src_data['timestamp'][0]), int(src_data['timestamp'][-1]), len(src_data))
    server.add_stream('/test/source', src, src_info, src_data, [src_info.start, src_info.end])
    return src_data
