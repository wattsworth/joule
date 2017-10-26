import json
from joule.utils.numpypipe import (StreamNumpyPipeReader,
                                   StreamNumpyPipeWriter,
                                   fd_factory)


def add_args(parser):
    grp = parser.add_argument_group('joule')
    # --pipes: JSON argument set by jouled
    grp.add_argument("--pipes",
                     default="unset",
                     help='RESERVED, managed by jouled')


def build_pipes(parsed_args):
    pipe_args = parsed_args.pipes
    if(pipe_args == 'unset'):
        return ({}, {})
    pipe_json = json.loads(pipe_args)
    dest_args = pipe_json['destinations']
    src_args = pipe_json['sources']
    pipes_out = {}
    pipes_in = {}
    for name, arg in dest_args.items():
        wf = fd_factory.writer_factory(arg['fd'])
        pipes_out[name] = StreamNumpyPipeWriter(arg['layout'], wf)
                                                
    for name, arg in src_args.items():
        rf = fd_factory.reader_factory(arg['fd'])
        pipes_in[name] = StreamNumpyPipeReader(arg['layout'], rf)

    return (pipes_in, pipes_out)
