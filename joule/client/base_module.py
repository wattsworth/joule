import json
import textwrap
import os
import configparser
import argparse
import asyncio
import signal
from joule.daemon import module, stream
from joule.utils.numpypipe import (StreamNumpyPipeReader,
                                   StreamNumpyPipeWriter,
                                   request_writer,
                                   request_reader,
                                   fd_factory)


class BaseModule:

    def __init__(self):
        self.stop_requested = False

    def run_as_task(self, parsed_args, loop):
        assert False, "implement in child class"

    def custom_args(self, parser):
        # parser.add_argument("--custom_flag")
        pass
        
    def stop(self):
        # override in client for alternate shutdown strategy
        self.stop_requested = True
        
    def build_args(self, parser):
        grp = parser.add_argument_group('joule')
        # --pipes: JSON argument set by jouled
        grp.add_argument("--pipes",
                         default="unset",
                         help='RESERVED, managed by jouled')
        # --module_config: set to run module standalone
        grp.add_argument("--module_config",
                         default="unset",
                         help='specify *.conf file for standalone operation')
        # --stream_configs: set to run module standalone
        grp.add_argument("--stream_configs",
                         default="unset",
                         help="specify directory of stream configs" +
                         "for standalone operation")
        parser.formatter_class = argparse.RawDescriptionHelpFormatter
        self.custom_args(parser)
        
    def start(self, parsed_args=None):
        if(parsed_args is None):
            parser = argparse.ArgumentParser()
            self.build_args(parser)
            parsed_args = parser.parse_args()
        loop = asyncio.get_event_loop()
        self.stop_requested = False
        try:
            task = self.run_as_task(parsed_args, loop)
            def stop_task():
                loop = asyncio.get_event_loop()
                # give task no more than 2 seconds to exit
                loop.call_later(2, task.cancel)
                # run custom exit routine
                self.stop()
            loop.add_signal_handler(signal.SIGINT, stop_task)
            loop.add_signal_handler(signal.SIGTERM, stop_task)
            loop.run_until_complete(task)
        except asyncio.CancelledError:
            pass
        except ModuleError as e:
            print(str(e))
        loop.close()
        
    async def build_pipes(self, parsed_args):
        pipe_args = parsed_args.pipes
        module_config_file = parsed_args.module_config
        stream_config_dir = parsed_args.stream_configs
        if(pipe_args == 'unset'):
            if(module_config_file == 'unset' or
               stream_config_dir == 'unset'):
                msg = "ERROR: specify --module_config_file and --stream_config_dir\n"+\
                      "\tor run in joule environment"
                raise ModuleError(msg)
            else:
                # request pipe sockets from joule server
                try:
                    return await self.build_socket_pipes(module_config_file,
                                                         stream_config_dir)
                except ConnectionRefusedError as e:
                    raise ModuleError("%s: (is jouled running?)" % str(e))
        else:
            return self.build_fd_pipes(pipe_args)

    async def build_socket_pipes(self, module_config_file, stream_config_dir):
        module_config = configparser.ConfigParser()
        with open(module_config_file, 'r') as f:
            module_config.read_file(f)
        parser = module.Parser()
        my_module = parser.run(module_config)
        # build the input pipes (must already exist)
        pipes_in = {}
        for name in my_module.source_paths.keys():
            path = my_module.source_paths[name]
            npipe = await request_reader(path)
            pipes_in[name] = npipe
        # build the output pipes (must have matching stream.conf)
        pipes_out = {}
        streams = self.parse_streams(stream_config_dir)
        for name in my_module.destination_paths.keys():
            path = my_module.destination_paths[name]
            try:
                npipe = await request_writer(streams[path])
            except KeyError:
                raise ModuleError(
                    "Missing configuration for destination [%s]" % path)
            pipes_out[name] = npipe
        return (pipes_in, pipes_out)

    def parse_streams(self, stream_config_dir):
        streams = {}
        for item in os.listdir(stream_config_dir):
            if(not item.endswith(".conf")):
                continue
            file_path = os.path.join(stream_config_dir, item)
            config = configparser.ConfigParser()
            config.read(file_path)
            parser = stream.Parser()
            try:
                my_stream = parser.run(config)
            except Exception as e:
                raise ModuleError("Error parsing [%s]: %s" % (item, e))
            streams[my_stream.path] = my_stream
        return streams

    def build_fd_pipes(self, pipe_args):
        pipe_json = json.loads(pipe_args)
        dest_args = pipe_json['destinations']
        src_args = pipe_json['sources']
        pipes_out = {}
        pipes_in = {}
        for name, arg in dest_args.items():
            wf = fd_factory.writer_factory(arg['fd'])
            pipes_out[name] = StreamNumpyPipeWriter(arg['layout'],
                                                    writer_factory=wf)

        for name, arg in src_args.items():
            rf = fd_factory.reader_factory(arg['fd'])
            pipes_in[name] = StreamNumpyPipeReader(arg['layout'],
                                                   reader_factory=rf)
        return (pipes_in, pipes_out)


class ModuleError(Exception):
    pass
