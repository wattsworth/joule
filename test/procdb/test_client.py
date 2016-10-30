import unittest
from joule.procdb import client as procdb_client
from joule.daemon import destination, stream, inputmodule
import asyncio
from unittest import mock

class TestClient(unittest.TestCase):
  def setUp(self):
    self.procdb = procdb_client.SQLClient(":memory:","mock_url")
    self.loop = asyncio.new_event_loop()
    asyncio.set_event_loop(None) #disable default event loop

  def tearDown(self):
    self.loop.close()

  @mock.patch("joule.procdb.client.nilmtools.filter",autospec=True)
  def test_register_input_module_1(self,mock_filter):
    """Database path is created when module is registered for the first time
       Modules can be retrieved by path or as a group"""
    #the stream doesn't exist in the proc database
    mock_filter.get_stream_info = mock.MagicMock(return_value = None)
    module = self.build_input_module("test","/test/path",
                                     datatype="float32",stream_count=3)
    #mock out the actual NilmDB calls
    mock_np_client = mock.Mock()
    self.procdb._get_numpy_client = (lambda : mock_np_client)
    #run the module registration
    self.procdb.register_input_module(module)
    #the path should be set up in the nilmdb database
    mock_np_client.stream_create.assert_called_with("/test/path","float32_3")
    #the db module should exist in the procdb
    #retrieve it directly
    stored_module = self.procdb.find_module_by_dest_path("/test/path")
    self.assertIsNotNone(stored_module)
    #add another module and get both back
    module2 = self.build_input_module("test2","/test/path2",
                                     datatype="float32",stream_count=3)
    self.procdb.register_input_module(module2)
    db_input_modules = self.procdb.input_modules()
    self.assertEqual(len(db_input_modules),2)

  @unittest.skip("TODO but code is written")
  @mock.patch("joule.procdb.client.nilmtools.filter",autospec=True)
  def test_register_input_module_2(self,mock_filter):
    """Database path is not created when module is registerd again"""
    #the stream exists in the database
  
  @mock.patch("joule.procdb.client.nilmtools.filter",autospec=True)
  def test_register_input_module_3(self,mock_filter):
    """Cannot register module if path exists with a different datatype"""
    info = mock.Mock(layout="uint_8", layout_type="uint", layout_count=8)
    mock_filter.get_stream_info = mock.MagicMock(return_value = info)
    module = self.build_input_module(datatype='float',stream_count=8)
    with self.assertRaisesRegex(procdb_client.ConfigError,"datatype"):
      self.procdb.register_input_module(module)


  @mock.patch("joule.procdb.client.nilmtools.filter",autospec=True)
  def test_register_input_module_4(self,mock_filter):
    """Cannot register module if path exists with a different stream count"""
    info = mock.Mock(layout="uint_8", layout_type="uint", layout_count=8)
    mock_filter.get_stream_info = mock.MagicMock(return_value = info)
    module = self.build_input_module(datatype='uint',stream_count=4)
    with self.assertRaisesRegex(procdb_client.ConfigError,"streams"):
      self.procdb.register_input_module(module)


  @mock.patch("joule.procdb.client.nilmtools.filter",autospec=True)
  def test_register_input_module_5(self,mock_filter):
    """Cannot register module with duplicate path"""
    #the stream exists in the database
    info = mock.Mock(layout="float_1", layout_type="float", layout_count=1)
    mock_filter.get_stream_info = mock.MagicMock(return_value = info)
    #another input module is already using it
    module1 = self.build_input_module(name = "original",
                                      path = "/test/data")
    module2 = self.build_input_module(name="duplicate",
                                      path="/test/data")
    self.procdb.register_input_module(module1)
    #so trying to register this module causes an error
    with self.assertRaisesRegex(procdb_client.ConfigError,"path"):
      self.procdb.register_input_module(module2)
  
  @mock.patch("joule.procdb.client.nilmtools.filter",autospec=True)
  def test_update_module(self,mock_filter):
    """Verify that the database updates module statistics"""
    TEST_PID = 100
    #don't create the stream, pretend its already there
    info = mock.Mock(layout="float_1", layout_type="float", layout_count=1)
    mock_filter.get_stream_info = mock.MagicMock(return_value = info)
    module = self.build_input_module()
    self.procdb.register_input_module(module)
    module.pid = TEST_PID
    self.procdb.update_module(module)
    retrieved_module = self.procdb.input_modules()[0]
    self.assertEqual(retrieved_module.pid,TEST_PID)

  @mock.patch("joule.procdb.client.nilmtools.filter",autospec=True)
  def test_module_find(self,mock_filter):
    """Check if modules can be found by column"""
    #don't create the stream, pretend its already there
    info = mock.Mock(layout="float_1", layout_type="float", layout_count=1)
    mock_filter.get_stream_info = mock.MagicMock(return_value = info)
    module = self.build_input_module(name="mymodule")
    self.procdb.register_input_module(module)
    retrieved_module = self.procdb.find_module_by_name("mymodule")
    self.assertIsNotNone(retrieved_module)
    retrieved_module = self.procdb.find_module_by_name("doesnotexist")
    self.assertIsNone(retrieved_module)
    
  @mock.patch("joule.procdb.client.nilmtools.filter",autospec=True)
  def test_module_logging(self,mock_filter):
    """Store and retrieve a log entry"""
    #don't create the stream, pretend its already there
    info = mock.Mock(layout="float_1", layout_type="float", layout_count=1)
    mock_filter.get_stream_info = mock.MagicMock(return_value = info)
    module = self.build_input_module(name="mymodule")
    self.procdb.register_input_module(module)
    self.procdb.log_to_module("log line",module.id)
    self.procdb.log_to_module("another line",module.id)
    logs = self.procdb.logs(module.id)
    self.assertEqual(len(logs),2)
  
  def build_input_module(self,name="test",path="/test/data",
                         datatype='float',stream_count = 1):
    dest = destination.Destination(path,datatype,keep_us=0,decimate=True)
    for i in range(stream_count):
      dest.add_stream(stream.build_stream("stream%d"%i))
    m = inputmodule.InputModule()
    m.name = name
    m.destination=dest
    m.description="autogenerated test module"
    return m

