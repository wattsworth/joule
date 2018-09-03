import asyncio
from aiohttp import web
from joule.client.reader_module import ReaderModule
import aiohttp_jinja2
import jinja2
import os
import random

CSS_DIR = os.path.join(os.path.dirname(__file__), 'assets', 'css')
JS_DIR = os.path.join(os.path.dirname(__file__), 'assets', 'js')
TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), 'assets', 'templates')


class Visualizer(ReaderModule):

    async def setup(self, parsed_args, app, output):
        loader = jinja2.FileSystemLoader(TEMPLATES_DIR)
        aiohttp_jinja2.setup(app, loader=loader)

    async def run(self, parsed_args, output):
        while True:
            await asyncio.sleep(1)

    def routes(self):
        return [
            web.get('/', self.index),
            web.get('/data.json', self.data),
            web.static('/assets/css', CSS_DIR),
            web.static('/assets/js', JS_DIR)
        ]

    @aiohttp_jinja2.template('index.jinja2')
    async def index(self, request):
        return {'inputs': self._create_mock_data()}

    async def data(self, request):
        return web.json_response(data=self._create_mock_data())

    async def hello(self, request):
        print("got hello page!")
        return web.Response(text="the hello handler")

    def _create_mock_data(self):
        inputs = []
        for x in range(4):
            value = random.randint(1, 101)
            min = value - random.randint(1, 101)
            max = value + random.randint(1, 101)
            inputs.append({
                'stream': 'test',
                'element': 'elem%d' % x,
                'value': value,
                'min': min,
                'max': max,
                'id': x
            })
        return inputs


if __name__ == "__main__":
    r = Visualizer()
    r.start()
