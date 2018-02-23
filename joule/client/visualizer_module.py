
import helpers
import argparse
import socket
from aiohttp import web


class VisualizerModule:

    def start(self, parsed_args=None):
        if(parsed_args is None):
            parser = argparse.ArgumentParser()
            self._build_args(parser)
            module_args = helpers.module_args()
            parsed_args = parser.parse_args(module_args)
        self.message = parsed_args.message
        app = web.Application(debug=True)
        
        self.setup_routes(app)
        if(parsed_args.socket is not None):
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            print(parsed_args.socket)
            sock.bind(b'\0'+parsed_args.socket.encode('ascii'))
            web.run_app(app, sock=sock)
        else:
            web.run_app(app,
                        host=parsed_args.host,
                        port=parsed_args.port)

    def _build_args(self, parser):
        grp = parser.add_argument_group('joule',
                                        'control module execution')
        # --module_config: set to run module standalone
        grp.add_argument("--module_config",
                         default="unset",
                         help='specify *.conf file for isolated execution')
        grp.add_argument("--host",
                         default="127.0.0.1",
                         help="IP address to listen (isolated execution only)")
        grp.add_argument("--port",
                         default="8080",
                         help="TCP Port to listen (isolated execution only)")
        grp.add_argument("--socket",
                         help="UNIX socket to listen (Joule execution)")
        # TODO: call super BaseModule
        grp.add_argument("--pipes")
        parser.formatter_class = argparse.RawDescriptionHelpFormatter
        self.custom_args(parser)

    def custom_args(self, parser):
        grp = parser.add_argument_group('module')
        grp.add_argument("--message", required=True)
    
    def setup_routes(self, app):
        app.router.add_get('/hello', self.hello)
        app.router.add_get('/', self.index)

    async def index(self, request):
        return web.Response(text="The message is " +
                            self.message)
    
    async def hello(self, request):
        return web.Response(text="the hello handler")
                   
    
if __name__ == "__main__":
    r = VisualizerModule()
    r.start()
    
