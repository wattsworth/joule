import json
import asyncio
from joule.models import (stream, pipes)
from typing import Dict, Tuple

Loop = asyncio.AbstractEventLoop
Pipes = Dict[str, pipes.Pipe]
""" Create Numpy Pipes based for a module """


def build_fd_pipes(pipe_args: str, loop: Loop) -> Tuple[Pipes, Pipes]:
    pipe_json = json.loads(json.loads(pipe_args))
    dest_args = pipe_json['outputs']
    src_args = pipe_json['inputs']
    pipes_out = {}
    pipes_in = {}
    for name, arg in dest_args.items():
        wf = pipes.writer_factory(arg['fd'], loop)
        pipes_out[name] = pipes.OutputPipe(stream=stream.from_json(arg['stream']),
                                           writer_factory=wf)

    for name, arg in src_args.items():
        rf = pipes.reader_factory(arg['fd'], loop)
        pipes_in[name] = pipes.InputPipe(stream=stream.from_json(arg['stream']),
                                         reader_factory=rf)

    return pipes_in, pipes_out
