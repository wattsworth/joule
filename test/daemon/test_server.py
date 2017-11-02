
import asyncio
import asynctest
import numpy as np
from unittest import mock
from test import helpers 
from joule.daemon import server
from joule.utils import network
from joule.utils.numpypipe import (request_reader,
                                   request_writer,
                                   LocalNumpyPipe)


ADDR = '127.0.0.1'
PORT = '1234'


class TestSever(asynctest.TestCase):

    """
    Open several connections to server, should receive
    JSON responses that the request is not valid
    """
    def test_clients_can_connect_to_server(self):
        NUM_CLIENTS = 10

        loop = asyncio.get_event_loop()
        client_connections = 0

        async def client():
            nonlocal client_connections
            r, w = await asyncio.open_connection(ADDR, PORT, loop=loop)
            msg = {'invalid config': None}
            await network.send_json(w, msg)
            r = await network.read_json(r)
            self.assertEqual(r['status'], network.STATUS_ERROR)
            client_connections += 1
            w.close()

        async def run():
            s = await server.build_server(ADDR, PORT, None, None)
            await asyncio.gather(*[client() for x in range(NUM_CLIENTS)])
            s.close()
            return s

        with self.assertLogs(level='WARN'):
            s = loop.run_until_complete(run())
            loop.run_until_complete(s.wait_closed())
            loop.close()
        self.assertEqual(client_connections, NUM_CLIENTS)
        
    def test_can_write_data(self):
        DTYPE = 'float32'
        NELEM = 3
        LAYOUT = '%s_%d' % (DTYPE, NELEM)
        LENGTH = 1000

        loop = asyncio.get_event_loop()
        
        async def run():
            mock_inserter = MockInserter()
            test_data = helpers.create_data(LAYOUT, length=LENGTH)
            s = await server.build_server(ADDR, PORT, None,
                                          lambda stream: (mock_inserter,
                                                          mock.Mock()))
#            r, w = await asyncio.open_connection(ADDR, PORT, loop=loop)
            test_stream = helpers.build_stream('test',
                                               datatype=DTYPE,
                                               num_elements=NELEM)
            npipe = await request_writer(test_stream, ADDR, PORT, loop=loop)
            await npipe.write(test_data)
            await asyncio.sleep(0.1)
            s.close()
            np.testing.assert_array_equal(test_data,
                                          mock_inserter.recvd_data())
            return s

        s = loop.run_until_complete(run())
        loop.run_until_complete(s.wait_closed())
        loop.close()

    def test_can_read_data(self):
        DTYPE = 'float32'
        NELEM = 3
        LAYOUT = '%s_%d' % (DTYPE, NELEM)
        LENGTH = 1000

        loop = asyncio.get_event_loop()
        
        async def run():
            npipe = LocalNumpyPipe(name='test', layout=LAYOUT)
            test_data = helpers.create_data(LAYOUT, length=LENGTH)
            test_stream = helpers.build_stream('test', path="/test/path",
                                               num_elements=NELEM,
                                               datatype=DTYPE)
            q = asyncio.Queue()
            q.put_nowait(test_data)
            npipe.write_nowait(test_data)
            
            def mock_reader_factory(path, time_range):
                # stream, queue, unsubscribe
                return(test_stream, q, mock.Mock())
            
            s = await server.build_server(ADDR, PORT,
                                          mock_reader_factory,
                                          None)
#            r, w = await asyncio.open_connection(ADDR, PORT, loop=loop)
            npipe = await request_reader("/test/path")
            rx_data = await npipe.read()
            npipe.consume(len(rx_data))
            s.close()
            await s.wait_closed()
            np.testing.assert_array_equal(test_data, rx_data)

        loop.run_until_complete(run())
        loop.close()

        
class MockInserter:
    def __init__(self):
        self.queue = None

    async def process(self, q, loop):
        self.queue = q

    def stop(self):
        pass

    def recvd_data(self):
        return self.queue.get_nowait()
    


