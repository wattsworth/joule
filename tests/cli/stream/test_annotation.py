from click.testing import CliRunner
import os
import logging

import warnings
from tests.cli.fake_joule import FakeJoule, FakeJouleTestCase
from joule.cli import main

ANNOTATION_LIST = os.path.join(os.path.dirname(__file__), 'annotations.json')
warnings.simplefilter('always')
aio_log = logging.getLogger('aiohttp.access')
aio_log.setLevel(logging.WARNING)


class TestStreamAnnotation(FakeJouleTestCase):

    def test_lists_annotations_csv(self):
        server = FakeJoule()
        with open(ANNOTATION_LIST, 'r') as f:
            server.response = f.read()
        self.start_server(server)
        runner = CliRunner()
        result = runner.invoke(main, ['stream', 'annotations', '/my/stream', '--csv'])
        self._assert_no_error(result)
        output = result.output
        self.stop_server()

    def test_lists_annotations_table(self):
        server = FakeJoule()
        with open(ANNOTATION_LIST, 'r') as f:
            server.response = f.read()
        self.start_server(server)
        runner = CliRunner()
        result = runner.invoke(main, ['stream', 'annotations', '/my/stream'])
        self.assertEqual(result.exit_code, 0)
        output = result.output
        self.stop_server()

    def test_delete_annotations(self):
        server = FakeJoule()
        self.start_server(server)
        runner = CliRunner()
        result = runner.invoke(main, ['stream', 'annotations', '/my/stream', '--delete'])
        self._assert_no_error(result)
        output = result.output
        self.stop_server()

    def _assert_no_error(self, result):
        if result.exit_code != 0:
            print("ERROR: ", result.output)
            print("EXCEPTION", result.exception)
        self.assertEqual(result.exit_code, 0)