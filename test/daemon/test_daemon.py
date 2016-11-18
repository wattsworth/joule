from joule.daemon.daemon import Daemon
from joule.daemon import daemon,stream
import tempfile
import unittest
import os
from unittest import mock
import asyncio
import asynctest
from joule.utils import config_manager

class TestDaemonSetup(unittest.TestCase):
  @mock.patch("joule.daemon.daemon.InputModule",autospec=True)
  @mock.patch("joule.daemon.daemon.destination.Parser",autospec=True)
  @mock.patch("joule.daemon.daemon.procdb_client",autospec=True)
  def test_it_creates_modules_and_dests(self,mock_procdb,mock_parser,mock_module):
    """creates a module and stream for every *.conf file and ignores others"""
    module_names = ['module1.conf','ignored','temp.conf~','module2.conf']
    stream_names = ['destination1.conf','otherfile','backup.conf~','destination2.conf','d3.conf']
    MODULE_COUNT = 2
    STREAM_COUNT = 3
    with tempfile.TemporaryDirectory() as module_dir:
      with tempfile.TemporaryDirectory() as stream_dir:
        for name in module_names:
          #create a stub module configuration (needed for configparser)
          with open(os.path.join(module_dir,name),'w') as f:
            f.write('[Main]\n')
        for name in stream_names:
          #create a stub stream configuration (needed for configparser)
          with open(os.path.join(stream_dir,name),'w') as f:
            f.write('[Main]\n')

        custom_config = """
         [Jouled]
           ModuleDirectory={:s}
           StreamDirectory={:s}
        """.format(module_dir,stream_dir)
        configs = config_manager.load_configs(custom_config,verify=False)
        daemon = Daemon()
        daemon._validate_module = mock.Mock(return_value=True)
        daemon._validate_destination = mock.Mock(return_value=True)
        daemon.initialize(configs)
        self.assertEqual(MODULE_COUNT,len(daemon.modules))
        self.assertEqual(STREAM_COUNT,len(daemon.streams))

    
  @mock.patch("joule.daemon.daemon.nilmtools.filter",autospec=True)
  def test_register_destination_1(self,mock_filter):
    """Cannot register destination if path exists with a different datatype"""
    info = mock.Mock(layout="uint8_8", layout_type="uint8", layout_count=8)
    mock_filter.get_stream_info = mock.MagicMock(return_value = info)
    dest = self.build_destination(datatype='float32',stream_count=8)
    with self.assertLogs(level='ERROR') as logs:
      daemon=Daemon()
      daemon._validate_destination(dest)
    self.assertRegex("/n".join(logs.output),"float32")

  @mock.patch("joule.daemon.daemon.nilmtools.filter",autospec=True)
  def test_register_destination_2(self,mock_filter):
    """Cannot register destination if path exists with a different stream count"""
    info = mock.Mock(layout="uint8_8", layout_type="uint8", layout_count=8)
    mock_filter.get_stream_info = mock.MagicMock(return_value = info)
    dest = self.build_destination(datatype='uint8',stream_count=4)
    with self.assertLogs(level='ERROR') as logs:
      daemon=Daemon()
      daemon._validate_destination(dest)
    self.assertRegex("/n".join(logs.output),"8")

  @mock.patch("joule.daemon.daemon.nilmtools.filter",autospec=True)
  def test_register_destination_3(self,mock_filter):
    """Cannot register destination with duplicate path"""
    info = mock.Mock(layout="float32_1", layout_type="float32",
                     layout_count=1)
    mock_filter.get_stream_info = mock.MagicMock(return_value = info)
    dest1 = self.build_destination(name='first',path="/same/path")
    dest2 = self.build_destination(name='second',path="/same/path")
    with self.assertLogs(level='ERROR') as logs:
      daemon=Daemon()
      daemon.destinations.append(dest1)
      daemon._validate_destination(dest2)
    self.assertRegex("/n".join(logs.output),"first")
    
  def test_register_module_1(self):
    """Cannot register modules with duplicate destinations"""
    daemon = Daemon()
    daemon.path_destinations = { "/path1/exists", mock.Mock(),
                                 "/path2/exists", mock.Mock()}
    module1 = mock.Mock()
    module1.destination_paths = { "path1": "/path/exists"}
    daemon.modules = [module1]
    module2 = mock.Mock()
    module2.destination_paths = {"path2": "/path2/exists",
                                 "duplicate_path": "/path/exists"}

    with self.assertLogs(level='ERROR') as logs:
      daemon._validate_module(module2)
    self.assertRegex("/n".join(logs.output),"path/exists")

  def test_register_module_2(self):
    """Module's destinations must have a configuration"""
    daemon = Daemon()
    daemon.path_destinations = { "/path/exists", mock.Mock()}
    module1 = mock.Mock()
    module1.destination_paths = { "path1": "/path/exists",
                                  "path2": "/path/not/configured"}

    with self.assertLogs(level='ERROR') as logs:
      daemon._validate_module(module1)
    self.assertRegex("/n".join(logs.output),"not/configured")

  @mock.patch("joule.daemon.daemon.nilmtools.filter",autospec=True)
  def test_register_module_3(self,mock_filter):
    """Database path is created when destination is first registered"""
    #the stream does not exist in the database
    mock_filter.get_stream_info = mock.MagicMock(return_value = None)
    dest = self.build_destination("test","/test/path")
    #mock out the actual NilmDB calls
    mock_client = mock.Mock()
    daemon = Daemon()
    daemon.nilmdb_client=mock_client
    daemon._validate_destination(dest)
    #the path should be set up in the nilmdb database
    mock_client.stream_create.assert_called_with("/test/path","float32_1")
    
  @mock.patch("joule.daemon.daemon.nilmtools.filter",autospec=True)
  def test_register_module_4(self,mock_filter):
    """Database path is not created when module is registered again"""
    #the stream exists in the database
    info = mock.Mock(layout="float32_1", layout_type="float32",
                     layout_count=1)
    mock_filter.get_stream_info = mock.MagicMock(return_value = info)
    dest = self.build_destination("test","/test/path")
    #mock out the actual NilmDB calls
    mock_client = mock.Mock()
    daemon = Daemon()
    daemon.nilmdb_client=mock_client
    daemon._validate_destination(dest)
    #the path should be set up in the nilmdb database
    mock_client.stream_create.assert_not_called()

  @mock.patch("joule.daemon.daemon.config_manager",autospec=True)
  def test_daemon_reads_config_file(self,mock_configs):
    CUSTOM_CONFIGURATION="custom_configuration"
    with tempfile.NamedTemporaryFile() as fp:
        fp.write(str.encode(CUSTOM_CONFIGURATION))
        fp.flush()
        daemon.load_configs(fp.name)
    mock_configs.load_configs.assert_called_with(config_string=CUSTOM_CONFIGURATION)

  def build_destination(self,name="test",path="/test/data",
                         datatype='float32',stream_count = 1):
    dest = destination.Destination(name,'auto-generated',path,datatype,keep_us=0,decimate=True)
    for i in range(stream_count):
      dest.add_stream(stream.build_stream("stream%d"%i))
    return dest


    
class TestDaemonRun(asynctest.TestCase):
  @asynctest.patch("joule.daemon.daemon.Worker",autospec=True)
  @asynctest.patch("joule.daemon.daemon.inserter.NilmDbInserter",autospec=True)
  def test_runs_modules_as_workers(self,mock_inserter,mock_worker):
    """daemon starts a worker and inserter for every module"""
    NUM_MODULES=4

    worker_runs = 0
    async def run_worker():
      nonlocal worker_runs
      worker_runs += 1
    instance = mock_worker.return_value
    instance.run = run_worker
    instance.module = mock.Mock() #should be set by daemon but the object is mocked
    instance.module.destination_paths = {}
    
    daemon = Daemon()
    daemon.procdb = mock.Mock()
    daemon.input_modules = [mock.Mock() for x in range(NUM_MODULES)]

    loop = asyncio.get_event_loop()
    daemon.stop_requested = True
    daemon.run(loop)
    

    self.assertEqual(worker_runs,NUM_MODULES)
    
