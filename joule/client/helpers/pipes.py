from typing import Tuple, Dict, Optional
import asyncio
import click
import json
import logging

from joule.models import pipes
from joule.api import BaseNode, stream
from joule import errors
from joule.services.parse_pipe_config import parse_pipe_config, parse_inline_config
from joule.utilities import timestamp_to_human

Pipes = Dict[str, pipes.Pipe]
Loop = asyncio.AbstractEventLoop
log = logging.getLogger('joule')


def build_fd_pipes(pipe_args: str, loop: Loop) -> Tuple[Pipes, Pipes]:
    try:
        pipe_json = json.loads(json.loads(pipe_args))
        # if debugging, pycharm escapes the outer JSON
        # pipe_json = json.loads(pipe_args.encode('utf-8').decode('unicode_escape'))
        dest_args = pipe_json['outputs']
        src_args = pipe_json['inputs']
    except (KeyError, json.JSONDecodeError):
        raise errors.ConfigurationError("invalid pipes argument: [%s]" % pipe_args)
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


async def build_network_pipes(inputs: Dict[str, str], outputs: Dict[str, str],
                              my_node: BaseNode, start_time: Optional[int], end_time: Optional[int],
                              force=False):
    if not force:
        _display_warning(outputs.values(), start_time, end_time)

    pipes_in = {}
    pipes_out = {}
    try:
        for name in inputs:
            my_stream = await _parse_stream(my_node, inputs[name])
            if start_time is None and end_time is None:
                # subscribe to live data
                pipes_in[name] = await my_node.data_subscribe(my_stream)
            else:
                pipes_in[name] = await my_node.data_read(my_stream,
                                                         start_time,
                                                         end_time)

        for name in outputs:
            my_stream = await _parse_stream(my_node, outputs[name])
            pipes_out[name] = await my_node.data_write(my_stream,
                                                       start_time,
                                                       end_time)
    except (errors.ApiError, errors.ConfigurationError) as e:
        # close any pipes that were created
        for name in pipes_in:
            await pipes_in[name].close()
        for name in pipes_out:
            await pipes_out[name].close()
        # re-raise the exception to be handled elsewhere
        raise e

    return pipes_in, pipes_out


def _display_warning(paths, start_time, end_time):
    # warn about data removal for historic execution
    if start_time is not None or end_time is not None:
        if end_time is None:
            msg = "after [%s]" % timestamp_to_human(start_time)
        elif start_time is None:
            msg = "before [%s]" % timestamp_to_human(end_time)
        else:
            msg = "between [%s - %s]" % (timestamp_to_human(start_time),
                                         timestamp_to_human(end_time))
        output_paths = ", ".join([x.split(':')[0] for x in paths])
        if not click.confirm("This will remove any data %s in the output streams [%s]" % (
                msg, output_paths)):
            exit(1)


async def _parse_stream(node: BaseNode, pipe_config) -> stream.Stream:
    (path, name, inline_config) = parse_pipe_config(pipe_config)
    if inline_config == "":
        raise errors.ConfigurationError(
            "[%s] is invalid: must specify an inline configuration for standalone execution" % pipe_config)
    (datatype, element_names) = parse_inline_config(inline_config)
    datatype = datatype.name.lower()  # API models are plain text attributes
    # use API to get or create the stream on the Joule node
    try:
        remote_stream = await node.stream_get(path + '/' + name)
        # make sure the layout agrees
        if remote_stream.datatype != datatype or \
                len(remote_stream.elements) != len(element_names):
            raise errors.ConfigurationError("Invalid stream configuration: [%s] has layout: %s not %s_%d" %
                                            (remote_stream.name, remote_stream.layout,
                                             datatype, len(element_names)))
    except errors.ApiError as e:
        if '404' in str(e):
            # create the stream
            new_stream = stream.Stream()
            new_stream.name = name
            new_stream.decimate = True
            new_stream.datatype = datatype
            for i in range(len(element_names)):
                e = stream.Element()
                e.name = element_names[i]
                e.index = i
                new_stream.elements.append(e)
            log.info("creating output stream [%s%s]" % (path, name))
            remote_stream = await node.stream_create(new_stream,
                                                     path)
        else:
            raise e
    return remote_stream
