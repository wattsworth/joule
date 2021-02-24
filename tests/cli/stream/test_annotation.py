from click.testing import CliRunner
import os
import logging
import csv
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
        lines = output.split("\n")
        reader = csv.reader(lines[1:])
        annotations = []
        for row in reader:
            annotations.append(row)
        # first annotation is an event
        self.assertEqual(['Instant', 'instant temperature', '1561752347819968'],
                         annotations[0])
        # second annoation is a range with no comment
        self.assertEqual(['hot!!!', '', '1561861116610000', '1561862838572000'],
                         annotations[1])
        self.stop_server()

    def test_lists_all_annotations_table(self):
        server = FakeJoule()
        with open(ANNOTATION_LIST, 'r') as f:
            server.response = f.read()
        self.start_server(server)
        runner = CliRunner()
        result = runner.invoke(main, ['stream', 'annotations', '/my/stream'])
        self.assertEqual(result.exit_code, 0)
        output = result.output
        # check for a few lines in the table
        self.assertIn("Instant", output)
        # timestamps should be displayed as dates
        self.assertNotIn("1561753681898272", output)
        self.assertIn("Fri, 28 Jun 2019 16:05:47", output)
        self.stop_server()

    def test_reteives_time_bounded_annotations(self):
        server = FakeJoule()
        with open(ANNOTATION_LIST, 'r') as f:
            server.response = f.read()
        self.start_server(server)
        runner = CliRunner()
        result = runner.invoke(main, ['stream', 'annotations', '/my/stream',
                                      '--start', '28 Jun 2019 16:00',
                                      '--end', '29 Jun 2019 16:00'])
        self.assertEqual(result.exit_code, 0)
        query_params = self.msgs.get()
        self.assertEqual(query_params["start"], "1561752000000000")
        self.assertEqual(query_params["end"], "1561838400000000")
        self.stop_server()

    def test_delete_all_annotations(self):
        server = FakeJoule()
        self.start_server(server)
        runner = CliRunner()
        result = runner.invoke(main, ['stream', 'annotations', '/my/stream', '--delete'])
        self._assert_no_error(result)
        query_params = self.msgs.get()
        self.assertEqual(query_params["stream_path"], "/my/stream")
        self.stop_server()

    def test_delete_time_bounded_annotations(self):
        server = FakeJoule()
        self.start_server(server)
        runner = CliRunner()
        result = runner.invoke(main, ['stream', 'annotations', '/my/stream',
                                      '--delete',
                                      '--start', '28 Jun 2019 16:00 EDT',
                                      '--end', '29 Jun 2019 16:00 EDT'])
        self._assert_no_error(result)
        query_params = self.msgs.get()
        self.assertEqual(query_params["stream_path"], "/my/stream")
        self.assertEqual(query_params["start"], "1561752000000000")
        self.assertEqual(query_params["end"], "1561838400000000")
        self.stop_server()

    def test_start_time_bound_errors(self):
        server = FakeJoule()
        self.start_server(server)
        runner = CliRunner()
        result = runner.invoke(main, ['stream', 'annotations', '/my/stream',
                                      '--start', 'baddate',
                                      '--end', '29 Jun 2019 16:00'])
        self.assertTrue('start time' in result.output)
        self.assertEqual(result.exit_code, 1)
        self.stop_server()

    def test_end_time_bound_errors(self):
        server = FakeJoule()
        self.start_server(server)
        runner = CliRunner()
        result = runner.invoke(main, ['stream', 'annotations', '/my/stream',
                                      '--start', '28 Jun 2019 16:00',
                                      '--end', 'baddate'])
        self.assertTrue('end time' in result.output)
        self.assertEqual(result.exit_code, 1)
        self.stop_server()

    def test_when_server_returns_error_code(self):
        server = FakeJoule()
        server.response = "test error"
        server.http_code = 500
        server.stub_annotation = True
        self.start_server(server)
        runner = CliRunner()
        result = runner.invoke(main, ['stream', 'annotations', 'folder/stream'])
        self.assertIn('500', result.output)
        self.assertIn("test error", result.output)
        self.assertEqual(result.exit_code, 1)
        self.stop_server()

    def _assert_no_error(self, result):
        if result.exit_code != 0:
            print("ERROR: ", result.output)
            print("EXCEPTION", result.exception)
        self.assertEqual(result.exit_code, 0)
