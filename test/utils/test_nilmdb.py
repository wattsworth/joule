"""
Test aionilmdb client implementation (uses aiohttp)

"""
import asynctest
import asyncio
from joule.utils import nilmdb


class TestNilmdb(asynctest.TestCase):

    def setUp(self):
        pass

    def demo(self):
        client = nilmdb.AsyncClient("http://localhost:8081")
        loop = asyncio.get_event_loop()

        async def run():
            x = await client.stream_list("/wattsworth/sinefit")
            print(x)
            client.close()
            print("closed!")
        loop.run_until_complete(run())
