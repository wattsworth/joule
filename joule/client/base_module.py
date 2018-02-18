import argparse
import asyncio
import signal
from . import helpers


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
        
    def start(self, parsed_args=None):
        if(parsed_args is None):
            parser = argparse.ArgumentParser()
            self._build_args(parser)
            module_args = helpers.module_args()
            parsed_args = parser.parse_args(module_args)
                
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
        except helpers.ClientError as e:
            print("ERROR:", str(e))
        loop.close()

    def _build_args(self, parser):
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

    async def _build_pipes(self, parsed_args):
        pipe_args = parsed_args.pipes
        module_config_file = parsed_args.module_config
        stream_config_dir = parsed_args.stream_configs

        # run the module within joule
        if(pipe_args != 'unset'):
            return helpers.build_fd_pipes(pipe_args)
        
        # run the module in isolation mode
        if(module_config_file == 'unset' or
           stream_config_dir == 'unset'):
            msg = ("Specify module_config AND stream_configs\n"
                   "\tor run in joule environment")
            raise helpers.ClientError(msg)
        
        # if time bounds are set make sure they are valid
        start_time = parsed_args.start_time
        end_time = parsed_args.end_time
        if((start_time is not None and end_time is None) or
           (end_time is not None and start_time is None)):
            raise helpers.ClientError("Specify start_time AND"
                                      " end_time or neither")

        # request pipe sockets from joule server
        try:
            return await helpers.build_socket_pipes(module_config_file,
                                                    stream_config_dir,
                                                    start_time,
                                                    end_time)
        except ConnectionRefusedError as e:
            raise helpers.ClientError("%s: (is jouled running?)" % str(e))

