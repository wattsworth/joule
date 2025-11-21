import warnings
from aiohttp.test_utils import unused_port
import dateparser
from click.testing import CliRunner
from ..fake_joule import FakeJoule, FakeJouleTestCase
from joule.cli import main
import tempfile
import os

warnings.simplefilter('always')

ARCHIVES_PATH = os.path.join(os.path.dirname(__file__), 'archives')

class TestUploadErrors(FakeJouleTestCase):

    def test_invalid_archive(self):
        runner = CliRunner()
        result = runner.invoke(main, ['archive','upload',ARCHIVES_PATH+'/ww-data_corrupt.zip'])
        self.assertNotEqual(result.exit_code,0)
        self.assertIn("does not look like a Joule archive",result.output)

    def test_no_archives_in_directory(self):
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmpdir:
            result = runner.invoke(main, ['archive','upload',tmpdir])
            self.assertNotEqual(result.exit_code,0)
            self.assertIn("no Joule archives found",result.output)
        
    
def _print_result_on_error(result):
    if result.exit_code != 0:
        print("output: ", result.output)
        print("exception: ", result.exception)
