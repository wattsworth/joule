from click.testing import CliRunner
from tests.cli.fake_joule import FakeJouleTestCase
from joule.cli import main
from ..fake_joule import print_result_on_error
import unittest
import tempfile
import shutil
import os
from joule.errors import ApiError
from unittest.mock import patch
from joule.api import helpers, TcpNode

VALID_ARCHIVE_NAME = "ww-data_2025_08_21-14-19-17"
ARCHIVES_PATH = os.path.join(os.path.dirname(__file__), 'archives')


class TestArchiveInspect(unittest.TestCase):
    
    def tests_inspects_archive_files(self):
        runner = CliRunner()
        result = runner.invoke(main, ['archive', 'inspect',
                                      os.path.join(ARCHIVES_PATH,"ww-data_2025_08_21-14-19-17.tgz")])
        print_result_on_error(result)
        self.assertEqual(result.exit_code, 0)
        # expect the node name and exporter label
        self.assertIn("joule-dev", result.output)
        self.assertIn("all_data", result.output)
        # expect 2 data streams and 1 event stream
        self.assertIn("2 data streams", result.output)
        self.assertIn("1 event stream", result.output)
        # nothing about layout or intervals
        self.assertNotIn("intervals", result.output)
        self.assertNotIn("layout", result.output.lower())

        
    def tests_inspect_archive_files_verbose(self):
        runner = CliRunner()
        result = runner.invoke(main, ['archive', 'inspect','-v',
                                      os.path.join(ARCHIVES_PATH,"ww-data_2025_08_21-14-19-17.tgz")])
        print_result_on_error(result)
        self.assertEqual(result.exit_code, 0)
        # expect the node name and exporter label
        self.assertIn("joule-dev", result.output)
        self.assertIn("all_data", result.output)
        # expect 2 data streams and 1 event stream
        self.assertIn("2 data streams", result.output)
        self.assertIn("1 event stream", result.output)
        # contains information about rows, layout, and intervals
        self.assertIn("intervals", result.output.lower())
        self.assertIn("layout", result.output.lower())
        self.assertIn("rows", result.output.lower())

    def tests_inspect_empty_archive_file(self):
        runner = CliRunner()
        result = runner.invoke(main, ['archive', 'inspect','-v',
                                      os.path.join(ARCHIVES_PATH,"ww-data_empty.tgz")])
        print_result_on_error(result)
        self.assertEqual(result.exit_code, 0)
        # expect the node name and exporter label
        self.assertIn("joule-dev", result.output)
        self.assertIn("all_data", result.output)
        # expect no data streams
        self.assertIn("no stream data", result.output)

    def tests_inspect_invalid_archive_file(self):
        runner = CliRunner()
        result = runner.invoke(main, ['archive', 'inspect','-v',
                                      os.path.join(ARCHIVES_PATH,"ww-data_corrupt.tgz")])
        self.assertEqual(result.exit_code, 1)
        # expect an error message
        self.assertIn("not a valid joule archive", result.output)
