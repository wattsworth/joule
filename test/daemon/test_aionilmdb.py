"""
Test aionilmdb client implementation (uses aiohttp)

"""
import asynctest
import asyncio
import joule.daemon.aionilmdb as aionilm


class TestAioNilmdb(asynctest.TestCase):

    def setUp(self):
        pass

    def demo(self):
        client = aionilm.AioNilmdb("http://localhost:8081")
        loop = asyncio.get_event_loop()
        async def run():
            x = await client.stream_list("/wattsworth/sinefit")
            print(x)
            client.close()
            print("closed!")
        loop.run_until_complete(run())
