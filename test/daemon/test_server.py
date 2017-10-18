

import asyncio
import asynctest
import numpy as np
from test import helpers 
from joule.daemon import server, server_utils
from joule.utils.stream_numpypipe_reader import StreamNumpyPipeReader
from joule.utils.stream_numpypipe_writer import StreamNumpyPipeWriter
from joule.utils.localnumpypipe import LocalNumpyPipe

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
            await server_utils.send_json(w, msg)
            r = await server_utils.read_json(r)
            self.assertEqual(r['status'], server_utils.STATUS_ERROR)
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
                                          lambda stream: mock_inserter)
            r, w = await asyncio.open_connection(ADDR, PORT, loop=loop) 
            stream_config = helpers.build_stream('test',
                                                 datatype=DTYPE,
                                                 num_elements=NELEM).to_json()
            msg = {'path': '/some/path', 'direction': 'write',
                   'layout': LAYOUT, 'configuration': stream_config}
            await server_utils.send_json(w, msg)
            resp = await server_utils.read_json(r)
            self.assertEqual(resp['status'], server_utils.STATUS_OK)
            npipe = StreamNumpyPipeWriter(LAYOUT, writer=w)
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
            npipe.write_nowait(test_data)
            s = await server.build_server(ADDR, PORT,
                                          lambda path, time_range: npipe,
                                          None)
            r, w = await asyncio.open_connection(ADDR, PORT, loop=loop) 
            msg = {'path': '/some/path', 'direction': 'read',
                   'decimation': 1, 'time_range': None}
            await server_utils.send_json(w, msg)
            resp = await server_utils.read_json(r)
            self.assertEqual(resp['status'], server_utils.STATUS_OK)
            npipe = StreamNumpyPipeReader(LAYOUT, reader=r)
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
    


