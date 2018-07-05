
import asyncio
from aiohttp import web
from joule.client.reader_module import ReaderModule


class VisualizerExample(ReaderModule):

    async def run(self, parsed_args, output):
        while True:
            await asyncio.sleep(10)

    def routes(self):

        return [
            web.get('/', self.index),
            web.get('/hello', self.hello)
        ]

    async def index(self, request):
        return web.Response(text="Index page!")

    async def hello(self, request):
        return web.Response(text="the hello handler")


if __name__ == "__main__":
    r = VisualizerExample()
    r.start()
