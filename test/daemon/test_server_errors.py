
import json
import asyncio
import asynctest


from joule.daemon import server, server_utils

ADDR = '127.0.0.1'
PORT = '1234'


class TestSeverErrors(asynctest.TestCase):

    """
    Logs error if client closes connection early
    """
    def test_handles_closed_sockets(self):

        async def client():
            r, w = await asyncio.open_connection(ADDR, PORT, loop=loop)
            msg = {'not waiting for response': None}
            await server_utils.send_json(w, msg)
            w.close()

        async def run():
            s = await server.build_server(ADDR, PORT, None, None)
            await client()
            s.close()
            return s

        loop = asyncio.get_event_loop()
        with self.assertLogs(level='WARN'):
            s = loop.run_until_complete(run())
            
            loop.run_until_complete(s.wait_closed())
            loop.close()

    def test_handles_corrupt_json(self):
        async def client():
            r, w = await asyncio.open_connection(ADDR, PORT, loop=loop)
            msg = {'not waiting for response': None}
            await server_utils.send_json(w, msg)
            w.close()

        async def run():
            s = await server.build_server(ADDR, PORT, None, None)
            await client()
            s.close()
            return s

        loop = asyncio.get_event_loop()
        with self.assertLogs(level='WARN'):
            s = loop.run_until_complete(run())
            
            loop.run_until_complete(s.wait_closed())
            loop.close()
        
        
