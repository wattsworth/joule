
import json
import asyncio
import asynctest


from joule.daemon import server, server_utils


class TestSever(asynctest.TestCase):

    """
    Open several connections to server, should receive
    JSON responses that the request is not valid
    """
    def test_clients_can_connect_to_server(self):
        ADDR = '127.0.0.1'
        PORT = '1234'
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

        s = loop.run_until_complete(run())
        loop.run_until_complete(s.wait_closed())
        loop.close()
        self.assertEqual(client_connections, NUM_CLIENTS)
        
