import json
import asyncio
import aiohttp
import click
import requests
import logging
from typing import Dict, Tuple, Optional

from joule.models import stream, Element, pipes
from joule.errors import ConfigurationError
from joule.cmds.helpers import get_json, get
from joule.services.parse_pipe_config import parse_pipe_config, parse_inline_config
from joule.utilities import timestamp_to_human

Loop = asyncio.AbstractEventLoop
Pipes = Dict[str, pipes.Pipe]
log = logging.getLogger('joule')

""" Create Numpy Pipes based for a module """


def build_fd_pipes(pipe_args: str, loop: Loop) -> Tuple[Pipes, Pipes]:
    try:
        pipe_json = json.loads(json.loads(pipe_args))
        dest_args = pipe_json['outputs']
        src_args = pipe_json['inputs']
    except (KeyError, json.JSONDecodeError):
        raise ConfigurationError("invalid pipes argument")
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
                              url: str, start_time: Optional[int], end_time: Optional[int],
                              loop: Loop, force=False):
    if not force:
        _display_warning(outputs.values(), start_time, end_time)

    pipes_in = {}
    for name in inputs:
        path, my_stream = _parse_stream(inputs[name])
        pipe = pipes.LocalPipe(my_stream.layout, name=path)
        pipes_in[name] = request_network_input(path, my_stream, url, pipe,
                                               loop, start_time, end_time)

    pipes_out = {}
    for name in outputs:
        path, my_stream = _parse_stream(outputs[name])
        pipes_out[name] = await request_network_output(path, my_stream, url, loop,
                                                       start_time, end_time)

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
            log.info("cancelled")
            exit(1)


def request_network_input(path: str, my_stream: stream.Stream, url: str,
                          pipe: pipes.Pipe, loop: Loop,
                          start_time: Optional[int] = None,
                          end_time: Optional[int] = None):
    # make sure the input is compatible
    resp = get_json(url + "/stream.json", params={"path": path})
    src_stream = stream.from_json(resp)
    if src_stream.layout != my_stream.layout:
        raise ConfigurationError("Input [%s] configured for [%s] but source is [%s]" % (
            path, my_stream.layout, src_stream.layout))

    # if the input is *live* make sure the stream is being produced
    if not src_stream.is_destination and (start_time is None and end_time is None):
        raise ConfigurationError("Input [%s] is not being produced, specify time bounds for historic execution" % path)
    # replace the stub stream (from config file) with actual stream
    pipe.stream = src_stream
    # all checks passed, subscribe to the input
    if start_time is None and end_time is None:
        task = loop.create_task(_live_reader(url, src_stream, pipe))
    else:
        task = loop.create_task(_historic_reader(url, src_stream, pipe, start_time, end_time))

    async def close():
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    pipe.close_cb = close

    return pipe


async def _live_reader(url: str, my_stream: stream.Stream, pipe_out: pipes.Pipe):
    async with aiohttp.ClientSession() as session:
        log.info("requesting live connection to [%s]" % my_stream.name)
        params = {'id': my_stream.id, 'subscribe': '1'}
        async with session.get(url + "/data", params=params) as response:
            if response.status != 200:  # pragma: no cover
                msg = await response.text()
                log.error("Error reading input [%s]: " % my_stream.name, msg)
                await pipe_out.close()
                return
            pipe_in = pipes.InputPipe(stream=my_stream, reader=response.content)
            try:
                while True:
                    data = await pipe_in.read()
                    pipe_in.consume(len(data))
                    await pipe_out.write(data)
                    print("wrote %d rows" % len(data))
                    if pipe_in.end_of_interval:
                        await pipe_out.close_interval()
            except (asyncio.CancelledError, pipes.EmptyPipe):
                pass
            except aiohttp.ClientError as e:
                log.error("pipe_builders::_live_reader: %s" % str(e))
    await pipe_out.close()
    print("live_reader done")


async def _historic_reader(url: str, my_stream: stream.Stream, pipe_out: pipes.Pipe, start_time, end_time):
    async with aiohttp.ClientSession() as session:
        log.info("requesting historic connection to [%s]" % my_stream.name)
        params = {'id': my_stream.id}
        if start_time is not None:
            params['start'] = start_time
        if end_time is not None:
            params['end'] = end_time
        async with session.get(url + "/data", params=params) as response:
            if response.status != 200:  # pragma: no cover
                msg = await response.text()
                log.error("Error reading input [%s]: " % my_stream.name, msg)
                await pipe_out.close()
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
                pass
            await pipe_out.close()


async def request_network_output(path: str, my_stream: stream.Stream, url: str, loop: Loop,
                                 start_time=None, end_time=None):
    # check if the output exists, create it if not
    resp = get(url + "/stream.json", params={"path": path})
    if resp.status_code == 404:
        dest_stream = await _create_stream(url, path, my_stream)
    else:
        dest_stream = stream.from_json(resp.json())
        if start_time is not None or end_time is not None:
            await _remove_data(url, dest_stream, start_time, end_time)

    if dest_stream.layout != my_stream.layout:
        raise ConfigurationError("Output [%s] configured for [%s] but destination is [%s]" % (
            path, my_stream.layout, dest_stream.layout))
    # raise a warning if the element names do not match
    actual_names = [e.name for e in dest_stream.elements]
    requested_names = [e.name for e in my_stream.elements]
    if actual_names != requested_names:  # pragma: no cover
        log.warning("[%s] elements do not match the existing stream" % path)

    # make sure the stream is not currently produced
    if dest_stream.is_destination:
        raise ConfigurationError("Output [%s] is already being produced" % path)

    # all checks passed, subscribe to the output
    async def close():
        await task

    pipe = pipes.LocalPipe(dest_stream.layout, name=path, stream=dest_stream, close_cb=close)
    task = loop.create_task(_output_writer(url, dest_stream, pipe))
    return pipe


async def _create_stream(url, path, my_stream: stream.Stream):
    log.info("creating destination stream [%s]" % path)
    folder_path = '/'.join(path.split('/')[:-1])
    body = {
        "path": folder_path,
        "stream": json.dumps(my_stream.to_json())
    }
    resp = requests.post(url + "/stream.json", data=body)
    if resp.status_code != 200:  # pragma: no cover
        raise ConfigurationError(("Error creating output [%s]:" % path), resp.content.decode())
    else:
        return stream.from_json(resp.json())


async def _remove_data(url, my_stream: stream.Stream, start_time, end_time):
    params = {"id": my_stream.id}
    if start_time is not None:
        params['start'] = int(start_time)
    if end_time is not None:
        params['end'] = int(end_time)
    resp = requests.delete(url + "/data", params=params)
    if resp.status_code != 200:  # pragma: no cover
        raise ConfigurationError(("Error removing output data [%s]:" % my_stream.name),
                                 resp.content.decode())


async def _output_writer(url, my_stream: stream.Stream, pipe):
    output_complete = False

    async def _data_sender():
        log.info("starting data sender")
        nonlocal output_complete
        try:
            while True:
                data = await pipe.read()
                if len(data) > 0:
                    yield data.tostring()
                if pipe.end_of_interval:
                    yield pipes.interval_token(my_stream.layout).tostring()
                pipe.consume(len(data))
        except pipes.EmptyPipe:
            pass
        output_complete = True

    while not output_complete:
        # disable total timeout, this is going to be a long session :)
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=None)) as session:
            try:
                async with session.post(url + "/data",
                                        params={"id": my_stream.id},
                                        data=_data_sender()) as response:
                    if response.status != 200:  # pragma: no cover
                        msg = await response.text()
                        log.error("Error writing output [%s]" % my_stream.name, msg)
                        return
            except aiohttp.ClientError as e:  # pragma: no cover
                log.info("Error submitting data to joule [%s], retrying" % str(e))


def _parse_stream(pipe_config) -> Tuple[str, stream.Stream]:
    (path, name, inline_config) = parse_pipe_config(pipe_config)
    if inline_config == "":
        raise ConfigurationError(
            "[%s] is invalid: must specify an inline configuration for standalone execution" % pipe_config)
    (datatype, element_names) = parse_inline_config(inline_config)
    elements = []
    for i in range(len(element_names)):
        elements.append(Element(name=element_names[i], index=i,
                                display_type=Element.DISPLAYTYPE.CONTINUOUS))
    my_stream = stream.Stream(name=name, keep_us=stream.Stream.KEEP_ALL, datatype=datatype)
    my_stream.elements = elements
    return path + '/' + my_stream.name, my_stream
