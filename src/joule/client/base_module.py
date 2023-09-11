import argparse
import asyncio
import signal

from typing import List, Tuple, Dict, Optional
from aiohttp import web
import socket
import logging
import os
import json

import joule.utilities
from joule.api import node
from joule import api
from joule.api.data_stream import DataStream, Element
from joule.client import helpers
# import directly so it can be mocked easily in unit tests
from joule.errors import ConfigurationError, EmptyPipeError, ApiError
from joule.models import pipes
from joule.services.parse_pipe_config import parse_pipe_config, parse_inline_config
from joule.utilities.interval_tools import interval_intersection, interval_difference

Pipes = Dict[str, 'pipes.Pipe']
Loop = asyncio.AbstractEventLoop
log = logging.getLogger('joule')

DataStreams = Dict[str, api.DataStream]


class BaseModule:
    """
    This is an abstract class and should not be inherited directly. Instead inherit from one of
    the following children :class:`joule.ReaderModule`, :class:`joule.FilterModule`, or :class:`joule.CompositeModule`
    """

    def __init__(self):
        self.stop_requested = False
        self.pipes: List[pipes.Pipe] = []
        self.STOP_TIMEOUT = 2
        self.runner = None
        self.node: node.BaseNode = None

    async def run_as_task(self, parsed_args, app: web.Application) -> asyncio.Task:
        assert False, "implement in child class"  # pragma: no cover

    def custom_args(self, parser: argparse.ArgumentParser):
        """

        Override to add custom command line arguments to the module.

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
        Override to change the default shutdown strategy which simply sets
        the ``stop_requested`` flag. If a module does not terminate within a few seconds
        of this method being called Joule will forcibly stop the module with SIGKILL.
        """
        # override in client for alternate shutdown strategy
        self.stop_requested = True

    def create_dev_app(self) -> web.Application:
        parser = argparse.ArgumentParser()
        self._build_args(parser)
        # must specify module config in JOULE_MODULE_CONFIG environment variable
        if 'JOULE_MODULE_CONFIG' not in os.environ:
            raise ConfigurationError("JOULE_MODULE_CONFIG not set, must specify config file")
        module_config_file = os.environ['JOULE_MODULE_CONFIG']
        if not os.path.isfile(module_config_file):
            raise ConfigurationError("JOULE_MODULE_CONFIG is not a module config file")

        module_args = helpers.load_args_from_file(module_config_file)
        parsed_args = parser.parse_args(module_args)
        self.node = api.get_node(parsed_args.node)

        self.stop_requested = False
        my_app = self._create_app()

        async def on_startup(app):
            app['task'] = await self.run_as_task(parsed_args, app)

        my_app.on_startup.append(on_startup)

        async def on_shutdown(app):
            self.stop()
            await app['task']

        my_app.on_shutdown.append(on_shutdown)
        return my_app

    def start(self, parsed_args: argparse.Namespace = None):
        """
        Execute the module. Do not override this function. Creates an event loop and
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

        # asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
        loop = asyncio.new_event_loop()
        self.stop_requested = False
        if parsed_args.api_socket != "unset":
            # should be set by the joule daemon
            if 'JOULE_CA_FILE' in os.environ:
                cafile = os.environ['JOULE_CA_FILE']
            else:
                cafile = ""
            self.node = node.UnixNode("local", parsed_args.api_socket, cafile)
        else:
            self.node = api.get_node(parsed_args.node)
        self.runner: web.AppRunner = loop.run_until_complete(self._start_interface(parsed_args))
        app = None
        if self.runner is not None:
            app = self.runner.app
        try:
            task = loop.run_until_complete(
                self.run_as_task(parsed_args, app))
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
        except (asyncio.CancelledError, pipes.EmptyPipe, EmptyPipeError) as e:
            pass
        finally:
            self._cleanup(loop)

    def _cleanup(self, loop: Loop):
        if self.runner is not None:
            loop.run_until_complete(self.runner.cleanup())
        for pipe in self.pipes:
            loop.run_until_complete(pipe.close())
        if self.node is not None:
            loop.run_until_complete(self.node.close())
        loop.run_until_complete(asyncio.sleep(0))
        loop.close()

    def _build_args(self, parser):  # pragma: no cover
        grp = parser.add_argument_group('joule',
                                        'control module execution')
        # --pipes: JSON argument set by jouled
        grp.add_argument("--pipes",
                         default="unset",
                         help='RESERVED, managed by jouled')
        # --socket: UNIX socket set by jouled for interface proxy
        grp.add_argument("--socket",
                         default="unset",
                         help='RESERVED, managed by jouled')
        # --api-socket: UNIX socket for API calls back to jouled
        grp.add_argument("--api-socket",
                         default="unset",
                         help='RESERVED, managed by jouled')
        # --port: port to host interface on during isolated execution
        grp.add_argument("--port", type=int,
                         help='port for isolated execution')
        # --host: IP address to host interface on during isolated exedcution
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
        # --node: node to connect to for isolated execution
        grp.add_argument("--node", default="",
                         help="joule node for isolated execution")
        # --new: historical isolation mode
        grp.add_argument("--new", action="store_true",
                         help="process historic data newer than the most recent destination data")
        # --live: subscribe to inputs (inputs must be actively produced)
        grp.add_argument("--live", action="store_true",
                         help="process live input data")
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

    async def _parse_streams(self, parsed_args) -> Tuple[DataStreams, DataStreams]:
        inputs = {}
        outputs = {}
        # if this is running in Joule use the pipe args structure with API calls
        if parsed_args.pipes != 'unset':
            try:
                pipe_json = json.loads(json.loads(parsed_args.pipes))
                # if debugging, pycharm escapes the outer JSON
                # pipe_json = json.loads(pipe_args.encode('utf-8').decode('unicode_escape'))
                output_args = pipe_json['outputs']
                input_args = pipe_json['inputs']
                for name, config in input_args.items():
                    if config['id'] is None:  # remote stream, no information available
                        inputs[name] = self._create_stub_stream(name, config['layout'])
                    else:
                        inputs[name] = await self.node.data_stream_get(config['id'])
                for name, config in output_args.items():
                    if config['id'] is None:  # remote stream, no information available
                        outputs[name] = self._create_stub_stream(name, config['layout'])
                    else:
                        outputs[name] = await self.node.data_stream_get(config['id'])
            except (KeyError, json.JSONDecodeError):
                raise ConfigurationError(f"invalid pipes argument: {parsed_args.pipes}")
        # otherwise use the specified module configuration file
        else:
            if parsed_args.module_config == "unset":
                raise ConfigurationError("module_config parameter missing")
            module_config = helpers.read_module_config(parsed_args.module_config)
            if parsed_args.stream_configs != "unset":
                configured_streams = helpers.read_stream_configs(parsed_args.stream_configs)
            else:
                configured_streams = {}
            if 'Inputs' in module_config:
                for name, path in module_config['Inputs'].items():
                    stream = await self._validate_or_create_stream(configured_streams, path)
                    inputs[name] = stream
            if 'Outputs' in module_config:
                for name, path in module_config['Outputs'].items():
                    stream = await self._validate_or_create_stream(configured_streams, path)
                    outputs[name] = stream
        return inputs, outputs

    def _create_stub_stream(self, name, layout):
        # if API information is not available (coming from a remote node) then
        # create a stream with the right layout to use as a substitute
        # NOTE: this could be improved but since the remote capability isn't
        # really used this should be fine for now
        (dtype, num_elements) = layout.split('_')
        return DataStream(name=f"STUB:{name}", description="automatically generated stub",
                          datatype=dtype,
                          elements=[Element(name=f"E{i}") for i in range(int(num_elements))])

    async def _validate_or_create_stream(self, configured_streams, raw_path):
        # process inline configuration if present
        path = await self._process_inline_configuration(raw_path, configured_streams)
        # try to get the actual stream from Joule
        try:
            stream = await self.node.data_stream_get(path)
            # validate that the local configuration matches the actual one
            if path in configured_streams:
                if configured_streams[path].layout != stream.layout:
                    raise ConfigurationError("Stream [%s] exists with layout [%s], not [%s]" % (
                        path, stream.layout, configured_streams[path].layout
                    ))
            return stream
        except ApiError:
            pass
        # create the stream
        if path not in configured_streams:
            raise ConfigurationError(f"{path} does not exist, provide config file or inline configuration")
        folder_path = '/'.join(path.split('/')[:-1])
        return await self.node.data_stream_create(configured_streams[path], folder_path)

    async def _process_inline_configuration(self, pipe_config, configured_streams):
        # if there is an inline configuration add it to the configured streams dict
        # returns the full path to the stream
        (path, name, inline_config) = parse_pipe_config(pipe_config)
        if inline_config == '':
            return pipe_config  # the pipe config is just the full path
        full_path = "/".join([path, name])
        # inline config exists
        (datatype, element_names) = parse_inline_config(inline_config)
        datatype = datatype.name.lower()  # API models are plain text attributes
        # make sure inline config agrees with stream config if present
        if full_path in configured_streams:
            stream = configured_streams[full_path]
            if datatype != stream.datatype.lower() or \
                    len(stream.elements) != len(element_names):
                raise ConfigurationError(
                    f"Invalid configuration: [{name}] inline format does not match config file")
        # otherwise create a stream object from the inline config
        stream = DataStream()
        stream.name = name
        stream.decimate = True
        stream.datatype = datatype
        for i in range(len(element_names)):
            e = Element()
            e.name = element_names[i]
            e.index = i
            stream.elements.append(e)
        configured_streams[full_path] = stream
        return full_path

    async def _compute_missing_intervals(self, input_streams, output_streams, parsed_args):
        # 1) If live is specified, don't do anything else- no intervals to process
        if parsed_args.live or parsed_args.pipes != 'unset':
            return [None]
        if len(input_streams) == 0:
            return []
        # 2) Convert string time arguments into Optional[timestamp] types
        start, end = helpers.validate_time_bounds(parsed_args.start_time,
                                                  parsed_args.end_time)
        # 3) Find the effective input and output intervals (intersection of the streams)
        input_intervals = None
        for stream in input_streams.values():
            intervals = await self.node.data_intervals(stream, start, end)
            if input_intervals is not None:
                input_intervals = interval_intersection(input_intervals, intervals)
            else:
                input_intervals = intervals
        output_intervals = None
        for stream in output_streams.values():
            intervals = await self.node.data_intervals(stream, start, end)
            if output_intervals is not None:
                output_intervals = interval_intersection(output_intervals, intervals)
            else:
                output_intervals = intervals
        if output_intervals is None:
            missing_intervals = input_intervals
        else:
            missing_intervals = interval_difference(input_intervals, output_intervals)
        # filter out intervals shorter than 1 second (boundary error with intervals)
        missing_intervals = [i for i in missing_intervals if (i[1] - i[0]) > 1e6]
        return missing_intervals

    async def _build_pipes_new(self, interval, input_streams, output_streams, pipe_args) -> Tuple[Pipes, Pipes]:
        input_pipes = {}
        output_pipes = {}
        # use network sockets for connection to inputs and outputs
        if pipe_args == 'unset':
            for (name, stream) in input_streams.items():
                if interval is None:  # subscribe to live data
                    input_pipes[name] = await self.node.data_subscribe(stream)
                else:
                    input_pipes[name] = await self.node.data_read(stream, interval[0], interval[1])
            for (name, stream) in output_streams.items():
                if interval is None:
                    output_pipes[name] = await self.node.data_write(stream)
                else:
                    output_pipes[name] = await self.node.data_write(stream, interval[0], interval[1])
        # use file descriptors provided by joule for connection to inputs and outputs
        else:
            try:
                pipe_json = json.loads(json.loads(pipe_args))
                # if debugging, pycharm escapes the outer JSON
                # pipe_json = json.loads(pipe_args.encode('utf-8').decode('unicode_escape'))
                output_args = pipe_json['outputs']
                input_args = pipe_json['inputs']
            except (KeyError, json.JSONDecodeError):
                raise ConfigurationError(f"invalid pipes argument: {pipe_args}")

            for name, arg in output_args.items():
                wf = pipes.writer_factory(arg['fd'])
                output_pipes[name] = pipes.OutputPipe(stream=output_streams[name],
                                                      layout=arg['layout'],
                                                      writer_factory=wf)
            for name, arg in input_args.items():
                rf = pipes.reader_factory(arg['fd'])
                input_pipes[name] = pipes.InputPipe(stream=input_streams[name],
                                                    layout=arg['layout'],
                                                    reader_factory=rf)
        # keep track of the pipes so they can be closed
        self.pipes = list(input_pipes.values()) + list(output_pipes.values())
        return input_pipes, output_pipes

    async def _build_pipes(self, parsed_args) -> Tuple[Pipes, Pipes]:
        # for unit testing mocks
        from joule.client.helpers.pipes import build_network_pipes

        pipe_args = parsed_args.pipes

        # figure out whether we should run with fd's or network sockets
        if pipe_args == 'unset':
            if parsed_args.module_config == 'unset':
                raise ConfigurationError('must specify --module_config')

            # 1) Convert string time arguments into Optional[timestamp] types
            start, end = helpers.validate_time_bounds(parsed_args.start_time,
                                                      parsed_args.end_time)
            # 2) Parse module config to find input and output streams
            inputs = {}
            outputs = {}
            module_config = helpers.read_module_config(parsed_args.module_config)
            if 'Inputs' in module_config:
                for name, path in module_config['Inputs'].items():
                    inputs[name] = path
            if 'Outputs' in module_config:
                for name, path in module_config['Outputs'].items():
                    outputs[name] = path
            # 3) Parse all stream config files in case they are needed
            configured_streams = {}
            if parsed_args.stream_configs != "unset":
                configured_streams = helpers.read_stream_configs(parsed_args.stream_configs)
            # 4) Build the input and output pipes using network sockets
            pipes_in, pipes_out = await build_network_pipes(
                inputs, outputs, configured_streams, self.node, start, end,
                parsed_args.new, parsed_args.force)
        else:
            # run the module within joule
            (pipes_in, pipes_out) = await helpers.build_fd_pipes(pipe_args, self.node)
        # keep track of the pipes so they can be closed
        self.pipes = list(pipes_in.values()) + list(pipes_out.values())
        return pipes_in, pipes_out

    def routes(self):
        """
        Override to register HTTP handlers for the module. Return
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

    def _create_app(self) -> web.Application:
        routes = self.routes()
        app = web.Application()
        app.add_routes(routes)
        return app

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
            if args.port is None:
                port = _find_port()
            else:
                port = args.port
            site = web.TCPSite(runner, port=port, host=args.host)
            await site.start()
            print("starting web server at %s:%d" % (args.host, port))
            return runner
        # socket config is 'none' when joule does not connect a socket
        if args.socket == 'none':
            if len(routes) > 0:
                logging.error("No socket available for the interface, check module configuration")
            return None
        # otherwise start a UNIX runner on the socket
        if os.path.exists(args.socket):
            log.error("Socket address [%s] is already in use, cannot start interface" % socket)
            return None
        app = web.Application()
        app.add_routes(routes)
        runner = web.AppRunner(app)
        await runner.setup()
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.bind(args.socket)
        os.chmod(args.socket, 0o660)
        site = web.SockSite(runner, sock)
        await site.start()
        print("starting web server at [%s]" % args.socket)
        return runner


def _find_port():
    # return an available TCP port, check to make sure it is available
    # before returning
    for port in range(8000, 9000):
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.bind(('localhost', port))
            sock.close()
            return port
        except OSError:
            continue
    raise ConfigurationError("Could not find an available port for the web interface, specify with --port")
