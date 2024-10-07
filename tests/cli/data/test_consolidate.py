import warnings
import dateparser
from click.testing import CliRunner
from ..fake_joule import FakeJoule, FakeJouleTestCase, print_result_on_error
from joule.cli import main
from joule.utilities import human_to_timestamp as h2ts
warnings.simplefilter('always')


class TestConsolidate(FakeJouleTestCase):

    def test_data_consolidate(self):
        server = FakeJoule()
        NUM_CONSOLIDATED = 5
        server.num_consolidated = NUM_CONSOLIDATED
        self.start_server(server)
        runner = CliRunner()
        start_str = "20 January 2015 12:00"
        end_str = "21 January 2015 12:00"
        result = runner.invoke(main, ['data', 'consolidate',
                                      '/folder/src',
                                      '--start', start_str,
                                      '--end', end_str])
        print_result_on_error(result)
        self.assertEqual(result.exit_code, 0)
        (path, start, end, max_gap) = self.msgs.get()
        self.assertEqual(path, '/folder/src')
        self.assertEqual(int(start), h2ts(start_str))
        self.assertEqual(int(end), h2ts(end_str))
        self.assertGreater(max_gap, 0) # default max_gap parameter
        # make sure decimate was not called
        self.assertEqual(self.msgs.qsize(), 0)
        # check the output for NUM_CONSOLIDATED intervals
        self.assertIn(f"{NUM_CONSOLIDATED} intervals", result.output)
        self.stop_server()

    def test_data_consolidate_and_decimate(self):
        # Run again with no intervals to consolidate, a max-gap parameter
        # and redecimate flag
        server = FakeJoule()
        server.num_consolidated = 0
        self.start_server(server)
        runner = CliRunner()
        MAX_GAP = 9191
        result = runner.invoke(main, ['data', 'consolidate',
                                      '/folder/src', '--max-gap',MAX_GAP,
                                      '--redecimate'])
        print_result_on_error(result)
        self.assertEqual(result.exit_code, 0)
        self.assertIn("No intervals less than", result.output)
        # consolidation
        (_, start, end, max_gap) = self.msgs.get()
        self.assertEqual(max_gap, 9191)
        self.assertIsNone(start)
        self.assertIsNone(end)
        # decimation
        (cmd, path) = self.msgs.get()
        self.assertEqual(cmd, "decimate")
        self.assertEqual(path, "/folder/src")
        # check the output for no intervals consolidated but redemication is run
        self.assertIn(f"No intervals less than {MAX_GAP} us", result.output)
        self.assertIn("Recomputing decimations", result.output)
        self.stop_server()

    def test_parameter_errors(self):
        server = FakeJoule()
        self.start_server(server)
        runner = CliRunner()
        # invalid start time
        result = runner.invoke(main, ['data', 'consolidate',
                                      '/folder/src',
                                      '--start', 'not a time'])
        self.assertEqual(result.exit_code, 1)
        self.assertIn("invalid start time", result.output)
        # invalid end time
        result = runner.invoke(main, ['data', 'consolidate',
                                      '/folder/src',
                                      '--end', 'not a time'])
        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("invalid end time", result.output)
        # invalid max-gap
        result = runner.invoke(main, ['data', 'consolidate',
                                      '/folder/src',
                                      '--max-gap', 'not a number'])
        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("max-gap", result.output)
        self.stop_server()

    def test_server_errors(self):
        server = FakeJoule()
        runner = CliRunner()
        server.stub_data_consolidate = True
        server.response = "server-error"
        server.http_code = 500
        self.start_server(server)

        result = runner.invoke(main, ['data', 'consolidate', '/folder/src'])
        self.assertIn("500", result.output)
        self.assertIn("server-error", result.output)
        self.stop_server()