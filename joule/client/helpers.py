import json
import os
import configparser
from joule.daemon import module, stream
from joule.utils.numpypipe import (StreamNumpyPipeReader,
                                   StreamNumpyPipeWriter,
                                   request_writer,
                                   request_reader,
                                   fd_factory)


def add_args(parser):
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
    

async def build_pipes(parsed_args):
    pipe_args = parsed_args.pipes
    module_config_file = parsed_args.module_config
    stream_config_dir = parsed_args.stream_configs
    if(pipe_args == 'unset'):
        if(module_config_file == 'unset' or
           stream_config_dir == 'unset'):
            msg = """specify --module_config_file and
            --stream_config_dir or run in joule environment"""
            raise ModuleError(msg)
        else:
            # request pipe sockets from joule server
            return await build_socket_pipes(module_config_file,
                                            stream_config_dir)
    else:
        return build_fd_pipes(pipe_args)

    
async def build_socket_pipes(module_config_file, stream_config_dir):
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
    streams = parse_streams(stream_config_dir)
    for name in my_module.destination_paths.keys():
        path = my_module.destination_paths[name]
        try:
            npipe = await request_writer(streams[path])
        except KeyError:
            raise ModuleError(
                "Missing configuration for destination [%s]" % path)
        pipes_out[name] = npipe
    return (pipes_in, pipes_out)

        
def parse_streams(stream_config_dir):
    streams = {}
    for item in os.listdir(stream_config_dir):
        if(not item.endswith(".conf")):
            continue
        file_path = os.path.join(stream_config_dir, item)
        config = configparser.ConfigParser()
        config.read(file_path)
        parser = stream.Parser()
        my_stream = parser.run(config)
        if(my_stream is not None):
            streams[my_stream.path] = my_stream
        else:
            print("Warning, could not parse [%s]" % file_path)
    return streams


def build_fd_pipes(pipe_args):
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
