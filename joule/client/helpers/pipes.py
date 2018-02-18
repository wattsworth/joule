
import configparser
import dateparser
import json
import os
import sys
from .errors import ClientError
from joule.daemon import module, stream
from joule.utils.numpypipe import (StreamNumpyPipeReader,
                                   StreamNumpyPipeWriter,
                                   fd_factory,
                                   request_writer,
                                   request_reader)

""" Create Numpy Pipes based for a module """


async def build_socket_pipes(module_config_file, stream_config_dir,
                             start_time=None, end_time=None):
    module_config = configparser.ConfigParser()
    with open(module_config_file, 'r') as f:
        module_config.read_file(f)
    parser = module.Parser()
    my_module = parser.run(module_config)

    # historic isolation mode warning
    if(start_time is not None and end_time is not None):
        # convert start_time and end_time into us timestamps
        start_ts = int(dateparser.parse(start_time).timestamp()*1e6)
        end_ts = int(dateparser.parse(end_time).timestamp()*1e6)
        time_range = [start_ts, end_ts]
        if(start_ts >= end_ts):
            raise ClientError("start_time [%s] is after end_time [%s]" %
                              (dateparser.parse(start_time),
                               dateparser.parse(end_time)))

        print("Running in historic isolation mode")
        print("This will ERASE data from [%s to %s] in the output streams:" %
              (dateparser.parse(start_time),
               dateparser.parse(end_time)))
        for (name, path) in my_module.output_paths.items():
            print("\t%s" % path)

        _check_for_OK()
        sys.stdout.write("\nRequesting historic stream"
                         " connection from jouled... ")
    else:
        time_range = None
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
    streams = _parse_streams(stream_config_dir)
    for name in my_module.output_paths.keys():
        path = my_module.output_paths[name]
        try:
            npipe = await request_writer(streams[path],
                                         time_range=time_range)
        except KeyError:
            raise ClientError(
                "Missing configuration for output [%s]" % path)
        pipes_out[name] = npipe
    print("[OK]")
    return (pipes_in, pipes_out)


def build_fd_pipes(pipe_args):
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


def _parse_streams(stream_config_dir):
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
            raise ClientError("Error parsing [%s]: %s" % (item, e))
        streams[my_stream.path] = my_stream
    return streams

def _check_for_OK():
    # raise error is user does not enter OK
    if (input("Type OK to continue: ") != "OK"):
        raise ClientError("must type OK to continue execution")
