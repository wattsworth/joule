import json
import textwrap
import sys
import os
import configparser
import argparse
import asyncio
import signal
import dateparser
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
        grp = parser.add_argument_group('joule',
                                        'control module execution')
        # --pipes: JSON argument set by jouled
        grp.add_argument("--pipes",
                         default="unset",
                         help='RESERVED, managed by jouled')
        # --module_config: set to run module standalone
        grp.add_argument("--module_config",
                         default="unset",
                         help='specify *.conf file for isolated execution')
        # --stream_configs: set to run module standalone
        grp.add_argument("--stream_configs",
                         default="unset",
                         help="specify directory of stream configs " +
                         "for isolated execution")
        # --start_time: historical isolation mode
        grp.add_argument("--start_time",
                         help="input start time for historic isolation")
        # --end_time: historical isolation mode
        grp.add_argument("--end_time",
                         help="input end time for historic isolation")

        parser.formatter_class = argparse.RawDescriptionHelpFormatter
        self.custom_args(parser)
        
    def start(self, parsed_args=None):
        if(parsed_args is None):
            parsed_args = self._parse_args()
                
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
            print("ERROR:",str(e))
        loop.close()
        
    async def build_pipes(self, parsed_args):
        pipe_args = parsed_args.pipes
        module_config_file = parsed_args.module_config
        stream_config_dir = parsed_args.stream_configs

        # run the module within joule
        if(pipe_args != 'unset'):
            return self.build_fd_pipes(pipe_args)
        
        # run the module in isolation mode
        if(module_config_file == 'unset' or
           stream_config_dir == 'unset'):
            msg = "Specify module_config_file AND stream_config_dir\n"+\
                  "\tor run in joule environment"
            raise ModuleError(msg)
        
        # if time bounds are set make sure they are valid
        start_time = parsed_args.start_time
        end_time = parsed_args.end_time
        if((start_time is not None and end_time is None) or
           (end_time is not None and start_time is None)):
            raise ModuleError("Specify start_time AND end_time or neither")

        # request pipe sockets from joule server
        try:
            return await self.build_socket_pipes(module_config_file,
                                                 stream_config_dir,
                                                 start_time,
                                                 end_time)
        except ConnectionRefusedError as e:
            raise ModuleError("%s: (is jouled running?)" % str(e))

    async def build_socket_pipes(self, module_config_file, stream_config_dir,
                                 start_time=None, end_time=None):
        module_config = configparser.ConfigParser()
        with open(module_config_file, 'r') as f:
            module_config.read_file(f)
        parser = module.Parser()
        my_module = parser.run(module_config)
        
        # historic isolation mode warning
        if(start_time is not None and end_time is not None):
            #convert start_time and end_time into us timestamps
            start_ts = int(dateparser.parse(start_time).timestamp()*1e6)
            end_ts = int(dateparser.parse(end_time).timestamp()*1e6)
            time_range = [start_ts, end_ts]
            if(start_ts >= end_ts):
               raise ModuleError("start_time [%s] is after end_time [%s]" %
                                 (dateparser.parse(start_time),
                                 dateparser.parse(end_time)))

            print("Running in historic isolation mode")
            print("This will ERASE data from [%s to %s] in the output streams:" %
                  (dateparser.parse(start_time),
                   dateparser.parse(end_time)))
            for (name, path) in my_module.output_paths.items():
                print("\t%s" % path)
            
            self._check_for_OK()
            sys.stdout.write("\nRequesting historic stream connection from jouled... ")
        else:
            time_range=None
            sys.stdout.write("Requesting live stream connections from jouled... ")
            
        # build the input pipes (must already exist)
        pipes_in = {}
        for name in my_module.input_paths.keys():
            path = my_module.input_paths[name]
            npipe = await request_reader(path,
                                         time_range=time_range)
            pipes_in[name] = npipe
        # build the output pipes (must have matching stream.conf)
        pipes_out = {}
        streams = self.parse_streams(stream_config_dir)
        for name in my_module.output_paths.keys():
            path = my_module.output_paths[name]
            try:
                npipe = await request_writer(streams[path],
                                             time_range=time_range)
            except KeyError:
                raise ModuleError(
                    "Missing configuration for output [%s]" % path)
            pipes_out[name] = npipe
        print("[OK]")
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
        dest_args = pipe_json['outputs']
        src_args = pipe_json['inputs']
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

    def _check_for_OK(self):
        return # BYPASS
        # raise error is user does not enter OK
        if (input("Type OK to continue: ") != "OK"):
            raise ModuleError("must type OK to continue execution")

    def _parse_args(self):
        """ Complicated because we want to look for module_config
            and add these args but this should be transparent
            (eg, the -h flag should show the real help)
        """
        # build a dummy parser to look for module_config
        temp_parser = argparse.ArgumentParser()
        temp_parser.add_argument("--module_config", default="unset")
        arg_list = sys.argv[1:]  # ignore the program name
        stdout = sys.stdout
        sys.stdout = open(os.devnull, 'w')
        try:
            args = temp_parser.parse_known_args()[0]
            if(args.module_config != "unset"):
                arg_list += self._append_args(args.module_config)
        except SystemExit:
            pass
        finally:
            sys.stdout.close()
            sys.stdout = stdout
        main_parser = argparse.ArgumentParser()
        self.build_args(main_parser)
        return main_parser.parse_args(arg_list)

    def _append_args(self, module_config_file):
        # if a module_config is specified add its args
        module_config = configparser.ConfigParser()
        with open(module_config_file, 'r') as f:
            module_config.read_file(f)
        parser = module.Parser()
        my_module = parser.run(module_config)
        return my_module.args
        
class ModuleError(Exception):
    pass


# parser for boolean args

def yesno(val):
    if(val is None):
        raise ValueError("must be 'yes' or 'no'")
    # standardize the string
    val = val.lower().rstrip().lstrip()
    if(val == "yes"):
        return True
    elif(val == "no"):
        return False
    else:
        raise ValueError("must be 'yes' or 'no'")
