from click.testing import CliRunner
import warnings
import os
import datetime

from joule.models import DataStream, Element, StreamInfo
from ..fake_joule import FakeJoule, FakeJouleTestCase
from joule.cli import main

STREAM_INFO = os.path.join(os.path.dirname(__file__), 'stream.json')
warnings.simplefilter('always')


class TestStreamDelete(FakeJouleTestCase):
    def test_deletes_stream(self):
        server = FakeJoule()
        with open(STREAM_INFO, 'r') as f:
            server.response = f.read()
        server.stub_stream_info = True  # use the response text
        self.start_server(server)
        runner = CliRunner()
        # does not delete with out confirmation
        runner.invoke(main,
                      ['stream', 'delete',
                       '/folder/stream'],
                      input='\n')
        self.assertTrue(self.msgs.empty())

        # executes deletes with confirmation
        result = runner.invoke(main,
                               ['stream', 'delete',
                                '/folder/stream'],
                               input='y\n')
        self.assertEqual(result.exit_code, 0)
        deleted_stream = self.msgs.get()
        self.assertEqual(deleted_stream, '/folder/stream')
        self.stop_server()

    def test_when_server_returns_error_code(self):
        server = FakeJoule()
        error_msg = "test error"
        error_code = 500
        server.response = error_msg
        server.stub_stream_destroy = True
        server.http_code = error_code
        # actually create a stream so the stubbed API call is the delete one
        src = DataStream(id=0, name="source", keep_us=100,
                         datatype=DataStream.DATATYPE.FLOAT32, updated_at=datetime.datetime.utcnow())
        src.elements = [Element(name="e%d" % x, index=x, display_type=Element.DISPLAYTYPE.CONTINUOUS) for x in range(3)]
        src_info = StreamInfo(0, 0, 0)
        server.add_stream('/folder/stream', src, src_info, None, [])

        self.start_server(server)
        runner = CliRunner()
        result = runner.invoke(main, ['stream', 'delete', '/folder/stream'],
                               input='y\n')
        self.assertTrue('%d' % error_code in result.output)
        self.assertTrue(error_msg in result.output)
        self.assertEqual(result.exit_code, 1)
        self.stop_server()
