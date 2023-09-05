from typing import Tuple, Dict, Optional, List
import asyncio
import click
import json
import logging

from joule.models import pipes
from joule.api import BaseNode, data_stream
from joule import errors
from joule.services.parse_pipe_config import parse_pipe_config, parse_inline_config
from joule.utilities import timestamp_to_human

Pipes = Dict[str, pipes.Pipe]
Loop = asyncio.AbstractEventLoop
log = logging.getLogger('joule')


async def build_fd_pipes(pipe_args: str, node: BaseNode) -> Tuple[Pipes, Pipes]:
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
        wf = pipes.writer_factory(arg['fd'])
        dest_stream = None
        if arg['id'] is not None:  # used in testing when no API is available
            dest_stream = await node.data_stream_get(arg['id'])
        pipes_out[name] = pipes.OutputPipe(stream=dest_stream,
                                           layout=arg['layout'],
                                           writer_factory=wf)

    for name, arg in src_args.items():
        rf = pipes.reader_factory(arg['fd'])
        src_stream = None
        if arg['id'] is not None:  # used in testing when no API is available
            src_stream = await node.data_stream_get(arg['id'])
        pipes_in[name] = pipes.InputPipe(stream=src_stream,
                                         layout=arg['layout'],
                                         reader_factory=rf)

    return pipes_in, pipes_out


async def build_network_pipes(inputs: Dict[str, str],
                              outputs: Dict[str, str],
                              configured_streams: Dict[str, data_stream.DataStream],
                              my_node: BaseNode,
                              start_time: Optional[int],
                              end_time: Optional[int],
                              live=False,
                              new=False,
                              force=False):
    if not force:
        _display_warning(outputs.values(), start_time, end_time)

    pipes_in = {}
    pipes_out = {}
    try:
        for name in inputs:
            my_stream = await _parse_stream(my_node, inputs[name], configured_streams)
            if new:
                if start_time is not None:
                    raise errors.ConfigurationError("Cannot specify [start] and [new], pick one")
                # determine start time based on last time stamp in outputs
                start_time, end_time = await _compute_new_interval(my_node, inputs, outputs)
                print("Running from [%s] to [%s]" %(
                    timestamp_to_human(start_time),
                    timestamp_to_human(end_time)
                ))
            if start_time is None and end_time is None:
                # subscribe to live data
                pipes_in[name] = await my_node.data_subscribe(my_stream)
            else:
                pipes_in[name] = await my_node.data_read(my_stream,
                                                         start_time,
                                                         end_time)

        for name in outputs:
            my_stream = await _parse_stream(my_node, outputs[name], configured_streams)
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


async def _parse_stream(node: BaseNode, pipe_config,
                        configured_streams: Dict[str, data_stream.DataStream]) -> data_stream.DataStream:
    (path, name, inline_config) = parse_pipe_config(pipe_config)
    full_path = "/".join([path, name])
    configured_stream = None
    # inline config exists
    if inline_config != "":
        (datatype, element_names) = parse_inline_config(inline_config)
        datatype = datatype.name.lower()  # API models are plain text attributes
        # make sure inline config agrees with stream config if present
        if path in configured_streams.keys():
            configured_stream = configured_streams[path]
            if datatype != configured_stream.datatype.lower() or \
                    len(configured_stream.elements) != len(element_names):
                raise errors.ConfigurationError("Invalid configuration: [%s] inline format does not match config file" %
                                                name)
        # otherwise create a stream object from the inline config
        configured_stream = data_stream.DataStream()
        configured_stream.name = name
        configured_stream.decimate = True
        configured_stream.datatype = datatype
        for i in range(len(element_names)):
            e = data_stream.Element()
            e.name = element_names[i]
            e.index = i
            configured_stream.elements.append(e)
    # no inline config
    elif full_path in configured_streams.keys():
        configured_stream = configured_streams[full_path]

    # use API to get or create the stream on the Joule node
    try:
        remote_stream = await node.data_stream_get(path + '/' + name)
        if configured_stream is not None:
            # make sure the provided config matches the existing stream
            if remote_stream.datatype != configured_stream.datatype or \
                    len(remote_stream.elements) != len(configured_stream.elements):
                raise errors.ConfigurationError("Invalid stream configuration: [%s] has layout: %s not %s_%d" %
                                                (remote_stream.name, remote_stream.layout,
                                                 configured_stream.datatype,
                                                 len(configured_stream.elements)))
    except errors.ApiError as e:
        if '404' in str(e):
            if configured_stream is None:
                raise errors.ConfigurationError(
                    "[%s] is invalid: must configure inline or stream configuration file" % pipe_config)

            log.info("creating output stream [%s%s]" % (path, name))
            remote_stream = await node.data_stream_create(configured_stream,
                                                          path)
        else:
            raise e
    return remote_stream


async def _compute_new_interval(node, inputs, outputs) -> Optional[Tuple[int, int]]:
    last_input = None
    last_output = None
    for name in inputs:
        stream_info = await node.data_stream_info(inputs[name])
        if last_input is None:
            last_input = stream_info.end
        else:
            last_input = max(last_input, stream_info.end)
    for name in outputs:
        stream_info = await node.data_stream_info(outputs[name])
        if last_output is None:
            last_output = stream_info.end
        else:
            last_output = max(last_output, stream_info.end)
    if last_input is None or last_output is None:
        return None
    return last_output, last_input
