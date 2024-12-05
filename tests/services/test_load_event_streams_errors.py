import logging
import configparser
from unittest import mock

from tests.helpers import DbTestCase
from joule.services import load_event_streams

logger = logging.getLogger('joule')

class TestLoadEventStreamErrors(DbTestCase):

    @mock.patch('joule.services.load_event_streams.load_configs')
    def test_validates_path(self, load_configs: mock.Mock):
        bad_paths = ["", "/slash/at/end/", "bad name", "/double/end//",
                     "//double/start", "/*bad&symb()ls"]
        for path in bad_paths:
            parser = configparser.ConfigParser()
            parser.read_string("""
                                [Main]
                                name=Bad DataStream
                                Path = %s
                                [Element1]
                                name=x
                                """ % path)
            load_configs.return_value = {'stream.conf': parser}
            with self.assertLogs(level="ERROR"):
                load_event_streams.run('', self.db)

        good_paths = ["/", "/short", "/meters-4/prep-a",
                      "/meter_4/prep-b", "/path  with/ spaces"]
        for path in good_paths:
            parser = configparser.ConfigParser()
            parser.read_string("""
                               [Main]
                                name=Bad DataStream
                                DataType=float32
                                Path = %s
                                [Element1]
                                name=x
                               """ % path)
            load_configs.return_value = {'stream.conf': parser}
            new_streams = load_event_streams.run('', self.db)
            self.assertEqual(len(new_streams), 1)

    @mock.patch('joule.services.load_event_streams.load_configs')
    def test_logs_invalid_streams(self, load_configs):
            parser = configparser.ConfigParser()
            parser.read_string("""
                        [Main]
                        name=Bad DataStream
                        Path = /invalid/fields/no/quotes
                        [Field1]
                        name = invalid
                        type = category:[cat1,cat2]
                        """)
            load_configs.return_value = {'stream.conf': parser}
            with self.assertLogs(level="ERROR"):
                new_streams = load_event_streams.run('', self.db)
                self.assertEqual(len(new_streams), 0)

    @mock.patch('joule.services.load_event_streams.load_configs')
    def test_checks_path_is_present(self, load_configs):
        parser = configparser.ConfigParser()
        parser.read_string("""
                            [Main]
                            name=No Path Setting
                            
                            """)
        load_configs.return_value = {'stream.conf': parser}
        with self.assertLogs(level="ERROR"):
            new_streams = load_event_streams.run('', self.db)
            self.assertEqual(len(new_streams), 0)
