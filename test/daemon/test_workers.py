
"""
Test workers module using asynctest
"""
import asynctest
import asyncio
import joule.daemon.worker as worker
import joule.daemon.inputmodule as inputmodule
from unittest import mock

class MockAsyncIterator():
  data = ["data"]
  def __init__(self,*args,**kwargs):
    self.runs = 0
    self.run_count = len(MockAsyncIterator.data)

  def __aiter__(self):
    return self

  async def __anext__(self):
    if(self.runs>=self.run_count):
      raise StopAsyncIteration
    else:
      res = MockAsyncIterator.data[self.runs]
      self.runs+=1
      return res
      

class TestWorkers(asynctest.TestCase):

  def setUp(self):
    self.mock_module = mock.Mock()
    self.mock_module.source_paths = {} #no inputs
    self.mock_module.exec_cmd="stub cmd"

  @asynctest.skip("covered by pipe tests")
  @asynctest.strict
  @asynctest.patch("joule.daemon.worker.numpypipe.NumpyPipe",new=MockAsyncIterator)
  @asynctest.patch("joule.daemon.worker.asyncio.create_subprocess_exec")
  def test_passes_data_to_subscribers(self,mock_create):
    """Waits on data from module and then passes it on to subscribers"""
    NUM_SUBSCRIBERS=4
    procdb = mock.Mock()
    my_worker = worker.Worker(self.mock_module ,procdb)
    subscribers = []
    my_worker._logger = asynctest.CoroutineMock()
    for i in range(NUM_SUBSCRIBERS):
      subscribers.append(my_worker.subscribe())

    loop = asyncio.get_event_loop()
    loop.run_until_complete(
      my_worker.run(restart=False))
    #mock numpypipe adds a generator object to the queues
    print(procdb.log_to_module.call_args_list)
    for q in subscribers:
      self.assertEqual(q.qsize(),1)

  @asynctest.patch("joule.daemon.worker.numpypipe.NumpyPipe",new=MockAsyncIterator)
  @asynctest.patch("joule.daemon.worker.asyncio.create_subprocess_exec")
  def test_restarts_failed_module_process(self,mock_client):
    my_worker = worker.Worker(self.mock_module ,mock.Mock())
    my_worker._logger = asynctest.CoroutineMock()
    loop = asyncio.get_event_loop()

    async def stop_worker():
      await asyncio.sleep(0.3)
      await my_worker.stop(loop)
      
    tasks = [ asyncio.ensure_future(stop_worker()),
              asyncio.ensure_future(my_worker.run(restart=True)) ]
    with self.assertLogs(level='ERROR'):
      loop.run_until_complete(asyncio.gather(*tasks))

  @asynctest.fail_on(unused_loop = False)
  def test_registers_inputs(self):
    mock_module = mock.create_autospec(spec = inputmodule.InputModule)
    mock_module.source_paths = {
      'path1': "/input/path/1",
      'path2': "/input/path/2"
    }
    m_worker1 = mock.create_autospec(spec=worker.Worker)
    m_worker2 = mock.create_autospec(spec=worker.Worker)
    my_worker = worker.Worker(mock_module,mock.Mock())
    worked_paths = {
      '/input/path/1': m_worker1,
      '/input/path/2': m_worker2
      }
    r = my_worker.register_inputs(worked_paths)
    self.assertTrue(r)
    self.assertTrue(m_worker1.subscribe.called)
    self.assertTrue(m_worker2.subscribe.called)

  @asynctest.fail_on(unused_loop = False)
  def test_registers_when_there_are_inputs(self):
    mock_module = mock.create_autospec(spec = inputmodule.InputModule)
    mock_module.source_paths = {}
    my_worker = worker.Worker(mock_module,mock.Mock())
    worked_paths = {}
    r = my_worker.register_inputs(worked_paths)
    self.assertTrue(r)

  @asynctest.fail_on(unused_loop = False)
  def test_does_not_register_if_inputs_are_missing(self):
    mock_module = mock.create_autospec(spec = inputmodule.InputModule)
    mock_module.source_paths = {
      'path1': "/input/path/1",
      'path2': "/input/path/2",
      'missing': "/input/missing"
    }
    m_worker1 = mock.create_autospec(spec=worker.Worker)
    m_worker2 = mock.create_autospec(spec=worker.Worker)
    my_worker = worker.Worker(mock_module,mock.Mock())
    worked_paths = {
      '/input/path/1': m_worker1,
      '/input/path/2': m_worker2
      }
    r = my_worker.register_inputs(worked_paths)
    #worker was not registered
    self.assertFalse(r)
    #no subscriptions requested
    self.assertFalse(m_worker1.subscribe.called)
    self.assertFalse(m_worker2.subscribe.called)
    
    
