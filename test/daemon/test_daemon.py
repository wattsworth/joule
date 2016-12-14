
from joule.daemon import daemon
import tempfile
import unittest
import os
from unittest import mock
import asyncio
import asynctest
import time
import threading
import configparser
from test import helpers
from joule.utils import config_manager


class TestDaemon(unittest.TestCase):

    @mock.patch("joule.daemon.daemon.module.Parser", autospec=True)
    @mock.patch("joule.daemon.daemon.stream.Parser", autospec=True)
    @mock.patch("joule.daemon.daemon.procdb_client", autospec=True)
    @mock.patch("joule.daemon.daemon.aionilmdb.AioNilmdb",autospec=True)
    def test_creates_modules_and_streams_from_configs(self,
                                                      mock_client,
                                                      mock_procdb,
                                                      stream_parser,
                                                      module_parser):
        """creates a module and stream for every *.conf file
        and ignores others"""
        module_names = ['module1.conf', 'ignored',
                        'temp.conf~', 'module2.conf']
        stream_names = ['destination1.conf', 'otherfile',
                        'backup.conf~', 'destination2.conf', 'd3.conf']
        MODULE_COUNT = 2
        STREAM_COUNT = 3

        with tempfile.TemporaryDirectory() as module_dir:
            with tempfile.TemporaryDirectory() as stream_dir:
                for name in module_names:
                    # create a stub module configuration (needed for
                    # configparser)
                    with open(os.path.join(module_dir, name), 'w') as f:
                        f.write('[Main]\n')
                for name in stream_names:
                    # create a stub stream configuration (needed for
                    # configparser)
                    with open(os.path.join(stream_dir, name), 'w') as f:
                        f.write('[Main]\n')

                custom_config = {'Jouled':
                                 {'ModuleDirectory': module_dir,
                                  'StreamDirectory': stream_dir}}
                configs = config_manager.load_configs(
                    custom_config, verify=False)
                my_daemon = daemon.Daemon()
                my_daemon._validate_module = mock.Mock(return_value=True)
                my_daemon._validate_stream = mock.Mock(return_value=True)
                my_daemon.initialize(configs)
                self.assertEqual(MODULE_COUNT, len(my_daemon.modules))
                self.assertEqual(STREAM_COUNT, len(my_daemon.streams))

    def test_validates_streams_and_modules(self):
        streams = [helpers.build_stream(name="in1",
                                        path="/data/in1",
                                        num_elements=4),
                   helpers.build_stream(name="out1in2",
                                        path="/data/o1in2",
                                        num_elements=4),
                   helpers.build_stream(name="out2",
                                        path="/data/out2",
                                        num_elements=4)]
        modules = [helpers.build_module(name="m1",
                                        source_paths={'in1': "/data/in1"},
                                        destination_paths={'out1':
                                                           "/data/o1in2"}),
                   helpers.build_module(name="m2",
                                        source_paths={'in2': "/data/o1in2"},
                                        destination_paths={'out2':
                                                           "/data/out2"})]
        # all streams exist in the database
        info = mock.Mock(layout="float32_4", layout_type="float32",
                         layout_count=4)
        my_daemon = daemon.Daemon()
        # mock AioNilmdb client
        mock_client = mock.Mock(autospec=daemon.aionilmdb.AioNilmdb)
        mock_client.get_stream_info_nowait = mock.MagicMock(return_value=
                                                            info)
        my_daemon.nilmdb_client = mock_client

        for my_stream in streams:
            self.assertTrue(my_daemon._validate_stream(my_stream))
            my_daemon.streams.append(my_stream)
            my_daemon.path_streams[my_stream.path] = my_stream

        for my_module in modules:
            self.assertTrue(my_daemon._validate_module(my_module))
            my_daemon.modules.append(my_module)

    def test_creates_nilmdb_entries_for_new_streams(self):
        """Database path is created when stream is first registered"""
        # mock AioNilmdb client
        mock_client = mock.Mock(autospec=daemon.aionilmdb.AioNilmdb)
        mock_client.get_stream_info_nowait = mock.MagicMock(return_value=None)

        # the stream does not exist in the database
        new_stream = helpers.build_stream(
            name="test", path="/test/path", num_elements=4)
        my_daemon = daemon.Daemon()
        my_daemon.nilmdb_client = mock_client
        my_daemon._validate_stream(new_stream)
        # the path should be set up in the nilmdb database
        mock_client.stream_create_nowait.assert_called_with(
            "/test/path", "float32_4")

    def test_does_not_create_nilmdb_entries_for_existing_streams(self):
        """Database path is not created when stream is registered again"""
        # the stream exists in the database
        info = mock.Mock(layout="float32_1", layout_type="float32",
                         layout_count=1)

        # mock AioNilmdb client
        mock_client = mock.Mock(autospec=daemon.aionilmdb.AioNilmdb)
        mock_client.get_stream_info_nowait = mock.MagicMock(return_value=info)

        existing_stream = helpers.build_stream(
            name="test", path="/test/path", num_elements=1)
        # mock out the actual NilmDB calls
        my_daemon = daemon.Daemon()
        my_daemon.nilmdb_client = mock_client
        my_daemon._validate_stream(existing_stream)
        # the path should be set up in the nilmdb database
        mock_client.stream_create_nowait.assert_not_called()


class TestDaemonModuleMethods(unittest.TestCase):

    @mock.patch("joule.daemon.daemon.config_manager", autospec=True)
    def test_load_configs(self, mock_configs):
        config_data = """[Main]
                    Setting1 = value1
                 """
        # put config_data into a file
        with tempfile.NamedTemporaryFile() as fp:
            fp.write(str.encode(config_data))
            fp.flush()
            daemon.load_configs(fp.name)
        # extract the [configs] argument passed into
        # [config_manager.load_configs]
        kwargs = mock_configs.load_configs.call_args[1]
        actual_configs = kwargs['configs']
        # generate expected configs using a dictionary
        expected_configs = configparser.ConfigParser()
        expected_configs.read_dict({"Main": {"setting1": "value1"}})
        # they should be equal
        self.assertEqual(actual_configs, expected_configs)

    @mock.patch("joule.daemon.daemon.Daemon", autospec=True)
    @mock.patch("joule.daemon.daemon.asyncio", autospec=True)
    @mock.patch("joule.daemon.daemon.load_configs")
    def test_main(self, mock_load_configs, mock_asyncio, mock_daemon):
        # set up the mocks
        my_daemon = mock_daemon.return_value
        my_daemon.initialize = mock.Mock()
        mock_loop = mock.Mock(spec=asyncio.BaseEventLoop)
        mock_asyncio.get_event_loop = mock.Mock(return_value=mock_loop)

        # run the main function, exits successfully
        with self.assertRaises(SystemExit) as cm:
            daemon.main(["--config=/config/file"])
        self.assertEqual(cm.exception.code, 0)
        # it should load the configuration
        daemon.load_configs.assert_called_with("/config/file")
        # ..set up a signal handler
        self.assertTrue(mock_loop.add_signal_handler.called)
        # ..run the loop
        self.assertTrue(my_daemon.run.called)
        # ..and close the loop
        self.assertTrue(mock_loop.close.called)


class TestDaemonRun(asynctest.TestCase):

    @asynctest.patch("joule.daemon.daemon.Worker", autospec=True)
    @asynctest.patch("joule.daemon.daemon.inserter.NilmDbInserter",
                     autospec=True)
    def test_runs_modules_as_workers(self, mock_inserter, mock_worker):
        """daemon starts a worker and inserter for every module"""
        worker_runs = 0

        async def run_worker():
            nonlocal worker_runs
            worker_runs += 1
        worker_stops = 0

        async def stop_worker(loop):
            nonlocal worker_stops
            worker_stops += 1

        my_worker = mock_worker.return_value
        my_worker.run = asynctest.mock.CoroutineMock()
        my_worker.stop = asynctest.mock.CoroutineMock()
        my_module = helpers.build_module("mock",
                                         destination_paths={"path1":
                                                            "/mock/path"})
        my_daemon = daemon.Daemon()
        my_daemon.procdb = mock.Mock()
        my_daemon.modules = [mock.Mock()]
        # a mock stream for the module
        my_daemon.path_streams["/mock/path"] = mock.Mock()
        my_worker.module = my_module  # set again because worker is mocked

        my_inserter = mock_inserter.return_value
        my_inserter.process = asynctest.mock.CoroutineMock()

        my_daemon.procdb_commit_interval = 0.1  # so we can stop quickly

        loop = asyncio.get_event_loop()

        def stop_daemon():
            time.sleep(0.2)
            my_daemon.stop()
        t = threading.Thread(target=stop_daemon)
        t.start()
        my_daemon.run(loop)
        # make sure workers were all started and stopped
        self.assertEqual(my_worker.run.call_count, 1)
        self.assertEqual(my_worker.stop.call_count, 1)
        # make sure inserters were all started and stopped
        self.assertEqual(my_inserter.process.call_count, 1)
        self.assertEqual(my_inserter.stop.call_count, 1)
        # make sure db committer task ran
        self.assertGreater(my_daemon.procdb.commit.call_count, 1)
