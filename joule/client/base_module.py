import argparse
import asyncio
import signal

from typing import List, Tuple, Dict, Optional
from aiohttp import web
import socket
import logging

from joule.client import helpers
from joule.errors import ConfigurationError
from joule.models import pipes

Pipes = Dict[str, 'pipes.Pipe']
Loop = asyncio.AbstractEventLoop
log = logging.getLogger('joule')


class BaseModule:

    def __init__(self):
        self.stop_requested = False
        self.pipes: List[pipes.Pipe] = []
        self.STOP_TIMEOUT = 2
        self.runner = None

    def run_as_task(self, parsed_args, app: web.Application, loop):
        assert False, "implement in child class"  # pragma: no cover

    def custom_args(self, parser: argparse.ArgumentParser):
        """

        Implement this method to add custom command line arguments to the module.

        .. code-block:: python

            class ModuleDemo(BaseModule):

                def custom_args(self, parser):
                     parser.description = "**module description**"
                     # add optional help text to the argument
                     parser.add_argument("--arg", help="custom argument")
                     # parse json input
                     parser.add_argument("--json_arg", type=json.loads)
                     # a yes|no argument that resolves to True|False
                     parser.add_argument("--flag_arg", type=joule.yesno)

                #... other module code


        Always use keyword arguments with modules so they can be specified
        in the **[Arguments]** section  of module configuration file

        Use the ``type`` parameter to specify a parser function. The parser
        function should accept a string input and return the appropriate object.

        """
        # parser.add_argument("--custom_flag")
        pass  # pragma: no cover

    def stop(self):
        """
        Implement this method to override the default shutdown strategy which simply sets
        the ``stop_requested`` flag. If a module does not terminate within a few seconds
        of this method being called Joule will forcibly stop the module with SIGKILL.
        """
        # override in client for alternate shutdown strategy
        self.stop_requested = True

    def start(self, parsed_args: argparse.Namespace=None):
        """
        Execute the module. Do not implement this function. Creates an event loop and
        executes the :meth:`run` coroutine.

        Args:
            parsed_args: omit to parse the command line arguments

        .. code-block:: python

            class ModuleDemo(BaseModule):
                # body of module...
                # at a minimum the run coroutine must be implemented

            if __name__ == "__main__":
                my_module = ModuleDemo()
                my_module.start()
        """

        if parsed_args is None:  # pragma: no cover
            parser = argparse.ArgumentParser()
            self._build_args(parser)
            module_args = helpers.module_args()
            parsed_args = parser.parse_args(module_args)

        loop = asyncio.get_event_loop()
        self.stop_requested = False

        self.runner: web.AppRunner = loop.run_until_complete(self._start_interface(parsed_args))
        app = None
        if self.runner is not None:
            app = self.runner.app
        try:
            task = self.run_as_task(parsed_args, app, loop)
        except ConfigurationError as e:
            log.error("ERROR: " + str(e))
            self._cleanup(loop)
            return

        def stop_task():
            # give task no more than 2 seconds to exit
            loop.call_later(self.STOP_TIMEOUT, task.cancel)
            # run custom exit routine
            self.stop()

        loop.add_signal_handler(signal.SIGINT, stop_task)
        loop.add_signal_handler(signal.SIGTERM, stop_task)
        try:
            loop.run_until_complete(task)
        except (asyncio.CancelledError, pipes.EmptyPipe):
            pass
        self._cleanup(loop)
        
    def _cleanup(self, loop: Loop):
        if self.runner is not None:
            loop.run_until_complete(self.runner.cleanup())
        for pipe in self.pipes:
            loop.run_until_complete(pipe.close())
        loop.close()

    def _build_args(self, parser):  # pragma: no cover
        grp = parser.add_argument_group('joule',
                                        'control module execution')
        # --pipes: JSON argument set by jouled
        grp.add_argument("--pipes",
                         default="unset",
                         help='RESERVED, managed by jouled')
        # --socket: UNIX socket set by jouled
        grp.add_argument("--socket",
                         default="unset",
                         help='RESERVED, managed by jouled')
        grp.add_argument("--port", type=int,
                         default=8080,
                         help='port for isolated execution')
        grp.add_argument("--host",
                         default="0.0.0.0",
                         help="IP address for isolated execution")
        # --module_config: set to run module standalone
        grp.add_argument("--module_config",
                         default="unset",
                         help='specify *.conf file for isolated execution')
        # --stream_configs: set to run module standalone
        grp.add_argument("--stream_configs",
                         default="unset",
                         help="specify directory of stream configs " +
                              "for isolated execution")
        grp.add_argument("--url", default="http://localhost:8088",
                         help="joule node for isolated execution")
        # --start_time: historical isolation mode
        grp.add_argument("--start_time", default=None,
                         help="input start time for historic isolation")
        # --end_time: historical isolation mode
        grp.add_argument("--end_time", default=None,
                         help="input end time for historic isolation")
        # --force: do not ask for confirmation
        grp.add_argument("--force", action="store_true",
                         help="do not ask for confirmation before dangerous operations")

        parser.formatter_class = argparse.RawDescriptionHelpFormatter
        self.custom_args(parser)

    async def _build_pipes(self, parsed_args, loop: Loop) -> Tuple[Pipes, Pipes]:
        from joule.utilities.pipe_builders import build_fd_pipes, build_network_pipes

        pipe_args = parsed_args.pipes

        # figure out whether we should run with fd's or network sockets
        if pipe_args == 'unset':
            start, end = helpers.validate_time_bounds(parsed_args.start_time,
                                                      parsed_args.end_time)
            if parsed_args.module_config == 'unset':
                raise ConfigurationError('must specify --module_config')
            inputs = {}
            outputs = {}
            module_config = helpers.read_module_config(parsed_args.module_config)
            if 'Inputs' in module_config:
                for name, path in module_config['Inputs'].items():
                    inputs[name] = path
            if 'Outputs' in module_config:
                for name, path in module_config['Outputs'].items():
                    outputs[name] = path
            pipes_in, pipes_out = await build_network_pipes(
                inputs, outputs, parsed_args.url, start, end, loop, parsed_args.force)
        else:
            # run the module within joule
            (pipes_in, pipes_out) = build_fd_pipes(pipe_args, loop)
        # keep track of the pipes so they can be closed
        self.pipes = list(pipes_in.values()) + list(pipes_out.values())
        return pipes_in, pipes_out

    def routes(self):
        """
        Implement this method to register HTTP handlers for the module. Return
        an array of handlers. This creates a visualization interface.

        .. code-block:: python

            class ModuleDemo(BaseModule):

                def routes(self):
                    return [
                        web.get('/', self.index),
                        # other handlers ...
                    ]

                async def index(self, request):
                    return web.Response(text="Hello World")

                #... other module code

        """
        return []  # override in child to implement a web interface

    async def _start_interface(self, args) -> Optional[web.AppRunner]:
        routes = self.routes()
        # socket config is 'unset' when run as a standalone process
        if args.socket == 'unset':
            if len(routes) == 0:
                return None  # no routes requested, nothing to do
            # create a local server
            app = web.Application()
            app.add_routes(routes)
            runner = web.AppRunner(app)
            await runner.setup()
            site = web.TCPSite(runner, port=args.port, host=args.host)
            await site.start()
            print("starting web server at %s:%d" % (args.host, args.port))
            return runner
        # socket config is 'none' when joule does not connect a socket
        if args.socket == 'none':
            if len(routes) > 0:
                logging.error("No socket available for the interface, check module configuration")
            return None
        # otherwise start a UNIX runner on the socket
        app = web.Application()
        app.add_routes(routes)
        runner = web.AppRunner(app)
        await runner.setup()
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.bind(b'\0' + args.socket.encode('ascii'))
        site = web.SockSite(runner, sock)
        await site.start()
        print("starting web server at [%s]" % args.socket)
        return runner
