from joule.daemon import daemon
import asyncio
import asynctest
from joule.utils import config_manager
from test import helpers
import unittest
from unittest import mock

class TestDaemonErrors(unittest.TestCase):

  @mock.patch("joule.daemon.daemon.nilmtools.filter",autospec=True)
  def test_stream_validation_fails_if_different_element_count(self,mock_filter):
    """Cannot register stream if NilmDB stream exists with a different element width"""
    info = mock.Mock(layout="float32_4", layout_type="float32", layout_count=4)
    mock_filter.get_stream_info = mock.MagicMock(return_value = info)
    my_stream = helpers.build_stream(name="test",num_elements=5)
    with self.assertLogs(level='ERROR') as logs:
      my_daemon=daemon.Daemon()
      my_daemon._validate_stream(my_stream)
    self.assertRegex("/n".join(logs.output),"5")

  @mock.patch("joule.daemon.daemon.nilmtools.filter",autospec=True)
  def test_stream_validation_fails_if_different_datatype(self,mock_filter):
    """Cannot register stream if path exists with a different datatype"""
    info = mock.Mock(layout="uint8_4", layout_type="uint8", layout_count=4)
    mock_filter.get_stream_info = mock.MagicMock(return_value = info)
    my_stream = helpers.build_stream(name="test",num_elements=5)
    with self.assertLogs(level='ERROR') as logs:
      my_daemon=daemon.Daemon()
      my_daemon._validate_stream(my_stream)
    self.assertRegex("/n".join(logs.output),"uint8")

  @mock.patch("joule.daemon.daemon.nilmtools.filter",autospec=True)
  def test_stream_validation_fails_if_duplicate_path(self,mock_filter):
    """Cannot register stream with duplicate path"""
    info = mock.Mock(layout="float32_1", layout_type="float32",
                     layout_count=1)
    mock_filter.get_stream_info = mock.MagicMock(return_value = info)
    stream1 = helpers.build_stream(name='first',path="/same/path",num_elements=1)
    stream2 = helpers.build_stream(name='second',path="/same/path",num_elements=1)
    with self.assertLogs(level='ERROR') as logs:
      my_daemon=daemon.Daemon()
      my_daemon.streams.append(stream1)
      my_daemon._validate_stream(stream2)
    self.assertRegex("/n".join(logs.output),"first")

  def test_build_stream_fails_on_bad_configs(self):
    with self.assertLogs(level='ERROR') as logs:
      my_daemon = daemon.Daemon()
      bad_config = {"Missing Main Section":"raises error"}
      my_daemon._build_stream(bad_config)
    self.assertRegex("/n".join(logs.output),"config")
      
  def test_validate_module_fails_on_duplicate_destinations(self):
    """Cannot register modules with duplicate destinations"""
    my_daemon = daemon.Daemon()
    my_daemon.path_streams = { "/path1/exists", mock.Mock(),
                               "/path2/exists", mock.Mock()}
    module1 = mock.Mock()
    module1.destination_paths = { "path1": "/path1/exists"}
    my_daemon.modules = [module1]
    module2 = mock.Mock()
    module2.destination_paths = {"path2": "/path2/exists",
                                 "duplicate_path": "/path1/exists"}

    with self.assertLogs(level='ERROR') as logs:
      my_daemon._validate_module(module2)
    self.assertRegex("/n".join(logs.output),"/path1/exists")

  def test_validate_module_fails_on_missing_stream(self):
    """Module's sources and destinations must have matching streams"""
    my_daemon = daemon.Daemon()
    my_daemon.path_streams = { "/path/exists", mock.Mock()}
    module_missing_destination = mock.Mock()
    module_missing_destination.source_paths = {}
    module_missing_destination.destination_paths =  { "path1": "/path/exists",
                                                      "path2": "/path/not/configured"}

    module_missing_source = mock.Mock()
    module_missing_source.source_paths = { "path1": "/path/exists",
                                           "path2": "/path/not/configured"}
    module_missing_source.destination_paths = {}
    
    with self.assertLogs(level='ERROR') as logs:
      my_daemon._validate_module(module_missing_destination)
    self.assertRegex("/n".join(logs.output),"not/configured")

    with self.assertLogs(level='ERROR') as logs:
      my_daemon._validate_module(module_missing_source)
    self.assertRegex("/n".join(logs.output),"not/configured")

    
  def test_build_module_fails_on_bad_configs(self):
    with self.assertLogs(level='ERROR') as logs:
      my_daemon = daemon.Daemon()
      bad_config = {"Missing Main Section":"raises error"}
      my_daemon._build_module(bad_config)
    self.assertRegex("/n".join(logs.output),"config")

class TestDaemonModuleMethodErrors(unittest.TestCase):

  def test_raises_error_with_nonexistent_config_file(self):
    with self.assertRaisesRegex(config_manager.InvalidConfiguration,
                                "file/does/not/exist"):
      daemon.load_configs("file/does/not/exist")

  @mock.patch("joule.daemon.daemon.load_configs")
  def test_exits_on_error_with_bad_configs(self, mock_load_configs):
    mock_load_configs.side_effect = config_manager.InvalidConfiguration("[fail]")
    with self.assertRaises(SystemExit) as cm:
      with self.assertLogs(level="ERROR"):
        daemon.main(["--config=/no/file"])
    self.assertNotEqual(cm.exception.code,0)


  @mock.patch("joule.daemon.daemon.Daemon",autospec=True)
  @mock.patch("joule.daemon.daemon.load_configs")
  def test_exits_on_error_if_daemon_does_not_initialize(self,
                                                        mock_load_configs,
                                                        mock_daemon):
                                                        
    my_daemon = mock_daemon.return_value
    my_daemon.initialize = mock.Mock(side_effect=daemon.DaemonError)

    with self.assertRaises(SystemExit) as cm:
      with self.assertLogs(level="ERROR"):
        daemon.main(["--config=/no/file"])
    self.assertNotEqual(cm.exception.code,0)

  
class TestDaemonRunErrors(asynctest.TestCase):
    
  def test_does_not_start_modules_with_missing_input_source(self):
    my_daemon = daemon.Daemon()
    streams = [ helpers.build_stream(name="out1",     path="/data/out1",     num_elements=4),
                helpers.build_stream(name="in2", path="/data/no_input_source", num_elements=4),
                helpers.build_stream(name="out2",    path="/data/out2",    num_elements=4) ]

    modules = [ helpers.build_module(name="module1",
                                     source_paths={},
                                     destination_paths={"path1":"/module1/output"}),
                helpers.build_module(name="module2",
                                     source_paths={"path1":"/nobody_writing_to/module2/input"},
                                     destination_paths={"path1":"/module2/output"})]

    for my_stream in streams:
      my_daemon.path_streams[my_stream.path] = my_stream
      my_daemon.streams.append(my_stream)

    my_daemon.modules = modules
    my_daemon.procdb = mock.Mock()
    my_daemon._start_worker = asynctest.mock.CoroutineMock()
    
    loop = asyncio.get_event_loop()
    my_daemon.stop_requested = True
    with self.assertLogs(level="WARNING") as logs:
      my_daemon.run(loop)
    loop.close()
    #did not start module2
    self.assertRegex("/n".join(logs.output),"module2")
    #started module1
    self.assertEqual(my_daemon._start_worker.call_count,1)

