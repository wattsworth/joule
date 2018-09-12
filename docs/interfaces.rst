Modules can provide web-based user interfaces.
When a Joule node is connected to
a Lumen server, the user authentication and authorization is handled
automatically and the interface is made available to any client with access to
the Lumen server. This makes it possible
to build secure and modular user interfaces that are decentralized
across the network but still present a single cohesive view to end users.

To add an interface to a module implement the routes function
and register handlers for any routes your module implements. You may
also add static routes to handle javascript and CSS assets. To
enable the user interface set the ``has_interface`` setting to ``yes`` in the
:ref:`sec-modules`

Examples
''''''''

.. code-block:: python
    :caption: Source: ``example_modules/example_interface.py``
    :linenos:

    import asyncio
    from aiohttp import web
    from joule.client.reader_module import ReaderModule


    class ExampleInterface(ReaderModule):

        async def run(self, parsed_args, output):
            # data processing...
            while True:
                await asyncio.sleep(1)

        def routes(self):
            return [web.get('/', self.index)]

        async def index(self, request):
            return web.Response(text="hello world!")


    if __name__ == "__main__":
        r = ExampleVisualizer()
        r.start()

.. code-block:: python
    :caption: Source: ``example_modules/complete_interface.py``
    :linenos:

    import asyncio
    from aiohttp import web
    from joule.client.reader_module import ReaderModule
    import aiohttp_jinja2
    import jinja2
    import os

    CSS_DIR = os.path.join(os.path.dirname(__file__), 'assets', 'css')
    JS_DIR = os.path.join(os.path.dirname(__file__), 'assets', 'js')
    TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), 'assets', 'templates')


    class CompleteInterface(ReaderModule):

        async def setup(self, parsed_args, app, output):
            loader = jinja2.FileSystemLoader(TEMPLATES_DIR)
            aiohttp_jinja2.setup(app, loader=loader)

        async def run(self, parsed_args, output):
            # data processing...
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
            return {'name': "Data Visualizer",
                    'version': 1.0}

        # json end point for AJAX requests
        async def data(self, request):
            # return summary statistics, etc.
            return web.json_response(data=[1,2,8])

    if __name__ == "__main__":
        r = ComplexInterface()
        r.start()


.. code-block:: none
    :caption: file layout for ComplexInterface assets

    ├── complex_interface.py
    └── assets
        ├── css
        │   └── main.css # and other css files
        ├── js
        │   └── main.js # other js files
        └── templates
            ├── layout.jinja2
            └── index.jinja2

Development
'''''''''''

When running as a standalone process, modules that provide a web interface
will start a local webserver on port 8000 (by default). This is accessible
from a browser at ``http://localhost:8000``.