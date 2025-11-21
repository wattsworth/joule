import unittest

from joule.utilities import archive_tools


class TestArchiveTools(unittest.TestCase):

    def test_import_logger(self):
        logger = archive_tools.ImportLogger()
        # can log 3 levels of messages
        logger.set_metadata(source_label='source',destination='dest', target_type='data_stream')
        logger.info("info message")
        self.assertTrue(logger.success)
        logger.warning("warning message")
        # warnings mean success if false
        self.assertFalse(logger.success)
        logger.error("error message")
        # can turn into JSON
        json_logs = logger.to_json()
        # can read from JSON
        logger2 = archive_tools.ImportLogger()
        logger2.from_json(json_logs)
        self.assertEqual(logger.info_messages,logger2.info_messages)
        self.assertEqual(logger.warning_messages,logger2.warning_messages)
        self.assertEqual(logger.error_messages,logger2.error_messages)
        
