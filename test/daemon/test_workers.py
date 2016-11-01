
"""
Test workers module using asynctest
"""
import asynctest
import asyncio
import joule.daemon.worker as worker
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

  @asynctest.strict
  @asynctest.patch("joule.daemon.worker.numpypipe.NumpyPipe",new=MockAsyncIterator)
  @asynctest.patch("joule.daemon.worker.asyncio.create_subprocess_exec")
  def test_passes_data_to_subscribers(self,mock_create):
    """Waits on data from module and then passes it on to subscribers"""
    NUM_SUBSCRIBERS=4
    mock_module = mock.Mock()
    mock_module.exec_path="stub cmd"
    my_worker = worker.Worker(mock_module ,mock.Mock())
    subscribers = []
    for i in range(NUM_SUBSCRIBERS):
      subscribers.append(my_worker.subscribe())

    loop = asyncio.get_event_loop()
    loop.run_until_complete(
      my_worker.run(restart=False))
    for q in subscribers:
      self.assertEqual(q.qsize(),1)

  @asynctest.patch("joule.daemon.worker.numpypipe.NumpyPipe",new=MockAsyncIterator)
  @asynctest.patch("joule.daemon.worker.asyncio.create_subprocess_exec")
  def test_restarts_failed_module_process(self,mock_client):
    mock_module = mock.Mock()
    mock_module.exec_path="stub cmd"
    my_worker = worker.Worker(mock_module ,mock.Mock())

    loop = asyncio.get_event_loop()

    async def stop_worker():
      await asyncio.sleep(0.3)
      await my_worker.stop()
    tasks = [ asyncio.ensure_future(stop_worker()),
              asyncio.ensure_future(my_worker.run(restart=True)) ]
    with self.assertLogs(level='ERROR'):
      loop.run_until_complete(asyncio.gather(*tasks))

    
