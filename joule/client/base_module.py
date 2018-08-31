import argparse
import asyncio
import signal
from typing import List, Tuple, Dict, TYPE_CHECKING
from aiohttp import web
import logging
import socket

from joule.client import helpers
from joule.errors import ConfigurationError
from joule.models import pipes

Pipes = Dict[str, 'pipes.Pipe']
Loop = asyncio.AbstractEventLoop


class BaseModule:

    def __init__(self):
        self.stop_requested = False
        self.pipes: List[pipes.Pipe] = []
        self.STOP_TIMEOUT = 2

    def run_as_task(self, parsed_args, loop):
        assert False, "implement in child class"  # pragma: no cover

    def custom_args(self, parser):
        # parser.add_argument("--custom_flag")
        pass  # pragma: no cover

    def stop(self):
        # override in client for alternate shutdown strategy
        self.stop_requested = True

    def start(self, parsed_args=None):
        if parsed_args is None:  # pragma: no cover
            parser = argparse.ArgumentParser()
            self._build_args(parser)
            module_args = helpers.module_args()
            parsed_args = parser.parse_args(module_args)

        loop = asyncio.get_event_loop()
        self.stop_requested = False

        runner = loop.run_until_complete(self._start_interface(parsed_args))
        task = self.run_as_task(parsed_args, loop)

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
        if runner is not None:
            loop.run_until_complete(runner.cleanup())
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
                raise ConfigurationError('must specify module config')
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
        return []  # override in child to implement a web interface

    async def _start_interface(self, args):
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
