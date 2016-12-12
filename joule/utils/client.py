from joule.utils.fdnumpypipe import FdNumpyPipe

def add_args(parser):
    grp = parser.add_argument_group('joule')
    #--pipes: JSON argument set by jouled
    grp.add_argument("--pipes",
                     default="unset",
                     help='RESERVED, managed by jouled')

def build_pipes(parsed_args):
    pipe_args = parsed_args.pipes
    dest_args = pipe_args['destinations']
    src_args = pipe_args['sources']
    pipes_out = []; pipes_in = [];
    for name,arg in dest_args.items():
      pipes_out.append(FdNumpyPipe(name=name,
                                   fd=arg['fd'],
                                   layout=arg['layout']))
    for name,arg in src_args.items():
      pipes_in.append(FdNumpyPipe(name=name,
                                   fd=arg['fd'],
                                   layout=arg['layout']))
    return (pipes_in, pipes_out)
