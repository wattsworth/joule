import warnings
import shutil
import tempfile
from click.testing import CliRunner
from ..fake_joule import FakeJoule, FakeJouleTestCase
from joule.cli import main
import os

warnings.simplefilter('always')

ARCHIVES_PATH = os.path.join(os.path.dirname(__file__), 'archives')

class TestUpload(FakeJouleTestCase):

    def test_archive_upload_directory(self):
        server = FakeJoule()
        self.start_server(server)
        runner = CliRunner()
        result = runner.invoke(main, ['archive','upload',ARCHIVES_PATH])
        _print_result_on_error(result)
        self.assertEqual(result.exit_code, 0)
        hashes = []
        for _ in range(3): # 3 valid archives in the folder
            # fake joule pushes the hash of the upload into 
            # the message queue
            hashes.append(self.msgs.get())
        expected_hashes = [
            '08ed689b189ee7cfde2b23885fc9222c',
            'ec00c952f92970b20e6437c0d5af8a0f',
            '38a6525bcc226da73522a924447885cd']
        for item in hashes:
            self.assertIn(item,expected_hashes)
        # displays the filenames that are uploaded
        self.assertIn('ww-data_2025_09_03-10-03-29', result.output)
        self.assertIn('ww-data_2025_09_03-10-03-59', result.output)
        self.assertIn('ww-data_empty', result.output)
        # ignores invalid archives (no ww-data_corrupt in out)
        self.assertNotIn('ww-data_corrupt', result.output)
        self.stop_server()

    def test_archive_flushes_files(self):
        server = FakeJoule()
        self.start_server(server)
        # create a temporary directory and copy an archive in to test flushing capability
        with tempfile.TemporaryDirectory() as tmpdir:
            # removes uploaded files from the directory
            runner = CliRunner()
            shutil.copy(ARCHIVES_PATH+'/ww-data_2025_09_03-10-03-29.zip',tmpdir+'/ww-data_copy.zip')
            shutil.copy(ARCHIVES_PATH+'/ww-data_2025_09_03-10-03-29.zip',tmpdir+'/ww-data_second_copy.zip')
            with open(tmpdir+'/other_file.txt','w') as f:
                f.write("should not be removed")
            result = runner.invoke(main, ['archive','upload',tmpdir,'-f'])
            _print_result_on_error(result)
            self.assertEqual(result.exit_code, 0)
            hash_val = self.msgs.get()
            self.assertEqual(hash_val,'ec00c952f92970b20e6437c0d5af8a0f')
            hash_val = self.msgs.get()
            self.assertEqual(hash_val,'ec00c952f92970b20e6437c0d5af8a0f')
            # make sure the file is removed
            self.assertFalse(os.path.exists(tmpdir+'/ww-data_copy.zip'))
            self.assertFalse(os.path.exists(tmpdir+'/ww-data_second_copy.zip'))
            # make sure other files are not removed
            self.assertTrue(os.path.exists(tmpdir+'/other_file.txt'))

            # also flushes a single file
            runner = CliRunner()
            shutil.copy(ARCHIVES_PATH+'/ww-data_2025_09_03-10-03-29.zip',tmpdir+'/ww-data_copy.zip')
            shutil.copy(ARCHIVES_PATH+'/ww-data_2025_09_03-10-03-29.zip',tmpdir+'/ww-data_second_copy.zip')
            result = runner.invoke(main, ['archive','upload',tmpdir+"/ww-data_copy.zip",'-f'])
            _print_result_on_error(result)
            self.assertEqual(result.exit_code, 0)
            hash_val = self.msgs.get()
            self.assertEqual(hash_val,'ec00c952f92970b20e6437c0d5af8a0f')
            # make sure the file is removed
            self.assertFalse(os.path.exists(tmpdir+'/ww-data_copy.zip'))
            # make sure other files are not removed
            self.assertTrue(os.path.exists(tmpdir+'/ww-data_second_copy.zip'))
            self.assertTrue(os.path.exists(tmpdir+'/other_file.txt'))

            self.stop_server()

    def test_archive_upload_file(self):
        server = FakeJoule()
        self.start_server(server)
        runner = CliRunner()
        result = runner.invoke(main, ['archive','upload',ARCHIVES_PATH+'/ww-data_2025_09_03-10-03-29.zip'])
        _print_result_on_error(result)
        self.assertEqual(result.exit_code, 0)
        hash_val = self.msgs.get()
        self.assertEqual(hash_val,'ec00c952f92970b20e6437c0d5af8a0f')
        self.stop_server()

def _print_result_on_error(result):
    if result.exit_code != 0:
        print("output: ", result.output)
        print("exception: ", result.exception)
