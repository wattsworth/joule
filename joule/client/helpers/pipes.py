import json
import asyncio
import aiohttp
import click
import requests
from typing import Dict, Tuple, Optional

from joule.models import (stream, Stream, Element, pipes, ConfigurationError)
from joule.cmds.helpers import get_json, get
from joule.services.parse_pipe_config import parse_pipe_config, parse_inline_config

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


async def build_network_pipes(inputs: Dict[str, str], outputs: Dict[str, str],
                              url: str, start_time, end_time, loop):
    pipes_in = {}
    for name in inputs:
        path, my_stream = _parse_stream(inputs[name])
        pipes_in[name] = await _request_network_input(path, my_stream, url, start_time, end_time, loop)

    pipes_out = {}
    for name in outputs:
        path, my_stream = _parse_stream(inputs[name])
        pipes_out[name] = await _request_network_output(path, my_stream, url, loop)

    return pipes_in, pipes_out


async def _request_network_input(path: str, my_stream: Stream, url: str,
                                 start_time: Optional[int], end_time: Optional[int], loop: Loop):
    # make sure the input is compatible
    resp = get_json(url + "/stream.json", params={"path": path})
    src_stream = stream.from_json(resp)
    if src_stream.layout != my_stream.layout:
        raise ConfigurationError("Input [%s] configured for [%s] but source is [%s]" % (
            path, my_stream.layout, src_stream.layout))
    # if the input is *live* make sure the stream is being produced
    if not src_stream.is_destination and (start_time is None and end_time is None):
        raise ConfigurationError("Input[%s] is not being produced, specify time bounds for historic execution" % path)
    # all checks passed, subscribe to the input
    pipe = pipes.LocalPipe(src_stream.layout, name="path")
    if start_time is None and end_time is None:
        task = loop.create_task(_live_reader(url, src_stream, pipe))
    else:
        task = loop.create_task(_historic_reader(url, src_stream, pipe, start_time, end_time))

    async def close():
        task.cancel()
        await task()

    pipe.close_cb = close

    return pipe


async def _live_reader(url: str, my_stream: Stream, pipe_out: pipes.Pipe):
    async with aiohttp.ClientSession() as session:
        params = {'id': my_stream.id}
        async with session.get(url + "/data/live", params=params) as response:
            if response.status != 200:
                msg = await response.text()
                print("Error reading input [%s]: " % my_stream.name, msg)
                return
            pipe_in = pipes.InputPipe(stream=my_stream, reader=response.content)
            try:
                while True:
                    data = await pipe_in.read()
                    pipe_in.consume(len(data))
                    await pipe_out.write(data)
                    if pipe_in.end_of_interval:
                        await pipe_out.close_interval()
            except (asyncio.CancelledError, pipes.EmptyPipe):
                return


async def _historic_reader(url: str, my_stream: Stream, pipe_out: pipes.Pipe, start_time, end_time):
    async with aiohttp.ClientSession() as session:
        params = {'id': my_stream.id, 'start': start_time, 'end': end_time}
        async with session.get(url + "/data", params=params) as response:
            if response.status != 200:
                msg = await response.text()
                print("Error reading input [%s]: " % my_stream.name, msg)
                return
            pipe_in = pipes.InputPipe(stream=my_stream, reader=response.content)
            try:
                while True:
                    data = await pipe_in.read()
                    pipe_in.consume(len(data))
                    await pipe_out.write(data)
                    if pipe_in.end_of_interval:
                        await pipe_out.close_interval()
            except (asyncio.CancelledError, pipes.EmptyPipe):
                await pipe_out.close()
                return


async def _request_network_output(path: str, my_stream: Stream, url: str, loop: Loop):
    # check if the output exists, create it if not
    resp = get(url + "/stream.json", params={"id": my_stream.id})
    if resp.status_code == 404:
        dest_stream = await _create_stream(url, path, my_stream)
    else:
        dest_stream = stream.from_json(resp.json())

    if dest_stream.layout != my_stream.layout:
        raise ConfigurationError("Output [%s] configured for [%d] but source is [%d]" % (
            path, my_stream.layout, dest_stream.layout))
    # raise a warning if the element names do not match
    actual_names = [e.name for e in dest_stream.elements]
    requested_names = [e.name for e in my_stream.elements]
    if actual_names != requested_names:
        click.confirm("Element names do not match, continue?", abort=True)
    # make sure the stream is not currently produced
    if dest_stream.is_destination:
        raise ConfigurationError("Output [%s] is already being produced")

    # all checks passed, subscribe to the output
    pipe = pipes.LocalPipe(my_stream.layout, name=path)
    task = loop.create_task(_live_writer(url, my_stream, pipe))

    async def close():
        await task()

    pipe.close_cb = close

    return pipe


async def _create_stream(url, path, my_stream: Stream):
    print("creating destination stream")
    body = {
        "path": path,
        "stream": json.dumps(my_stream.to_json())
    }
    resp = requests.post(url + "/stream.json", data=body)
    if resp.status_code != 200:
        raise ConfigurationError("Error creating output [%s]:" % path, resp.content.decode())
    else:
        return stream.from_json(resp.json())


async def _live_writer(url, my_stream: Stream, pipe):
    async with aiohttp.ClientSession() as session:
        async def _data_sender():
            try:
                while True:
                    data = await pipe.read()
                    pipe.consume(len(data))
                    if len(data) > 0:
                        yield data.tostring()
                    if pipe.end_of_interval:
                        yield pipes.interval_token(my_stream.layout).tostring()
            except pipes.EmptyPipe:
                pass

        async with session.post(url + "/data",
                                params={"id": my_stream.id},
                                data=_data_sender()) as response:
            if response.status != 200:
                msg = await response.text()
                print("Error writing output [%s]" % my_stream.name, msg)


def _parse_stream(pipe_config) -> Tuple[str, stream.Stream]:
    (path, name, inline_config) = parse_pipe_config(pipe_config)
    if inline_config == "":
        raise ConfigurationError(
            "[%s] is invalid: must specify an inline configuration for standalone execution" % pipe_config)
    (datatype, element_names) = parse_inline_config(inline_config)
    elements = []
    for i in range(len(element_names)):
        elements.append(Element(name=element_names[i], index=i))
    my_stream = Stream(name=name, keep_us=Stream.KEEP_ALL, datatype=datatype)
    my_stream.elements = elements
    return path + '/' + my_stream.name, my_stream
