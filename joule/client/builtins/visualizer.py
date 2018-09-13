import asyncio
from aiohttp import web
from joule.client.filter_module import FilterModule
import aiohttp_jinja2
import jinja2
import os
import random

CSS_DIR = os.path.join(os.path.dirname(__file__), 'assets', 'css')
JS_DIR = os.path.join(os.path.dirname(__file__), 'assets', 'js')
TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), 'assets', 'templates')

ARGS_DESC = """
TODO
"""


class Visualizer(FilterModule):

    async def setup(self, parsed_args, app, inputs, outputs):
        loader = jinja2.FileSystemLoader(TEMPLATES_DIR)
        aiohttp_jinja2.setup(app, loader=loader)
        app["title"] = parsed_args.title
        self.elements = []
        for pipe in inputs.values():
            for element in pipe.stream.elements:
                self.elements.append({
                    'stream': pipe.stream.name,
                    'element': element.name,
                    'value': '--',
                    'min': '--',
                    'max': '--',
                    'id': element.id
                })
        if len(self.elements) == 0:
            self.mock_data = True
            self.elements = self._create_mock_elements(4)

        else:
            self.mock_data = False

    def custom_args(self, parser):
        parser.add_argument("--title", default="Data Visualizer", help="page title")
        parser.description = ARGS_DESC

    async def run(self, parsed_args, inputs, outputs):
        if self.mock_data:
            while True:
                self._update_mock_data()
                await asyncio.sleep(1)
        while True:
            # compute max, mean, and min
            pass

    def routes(self):
        return [
            web.get('/', self.index),
            web.get('/data.json', self.data),
            web.post('/reset.json', self.reset),
            web.static('/assets/css', CSS_DIR),
            web.static('/assets/js', JS_DIR)
        ]

    @aiohttp_jinja2.template('index.jinja2')
    async def index(self, request):
        return {'title': request.app['title'], 'elements': self.elements}

    async def data(self, request):
        return web.json_response(data=self.elements)

    async def reset(self, request):
        # clear the max and min values
        return web.json_response(data=self.elements)

    def _update_mock_data(self):
        for element in self.elements:
            element['value'] = random.randint(1, 101)
            element['min'] = element['value'] - random.randint(1, 101)
            element['max'] = element['value'] + random.randint(1, 101)

    def _create_mock_elements(self, num_elements: int):
        elements = []
        for x in range(num_elements):
            elements.append({
                'stream': 'test',
                'element': 'elem%d' % x,
                'value': '--',
                'min': '--',
                'max': '--',
                'id': x
            })
        return elements


def main():  # pragma: no cover
    r = Visualizer()
    r.start()


if __name__ == "__main__":
    main()
