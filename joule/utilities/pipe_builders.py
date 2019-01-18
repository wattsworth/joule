import json
import asyncio
import aiohttp
import click
import requests
import logging
from typing import Dict, Tuple, Optional

from joule.models import stream, Element, pipes
from joule import errors
from joule.api import node
# from joule.cmds.helpers import get_json, get
from joule.services.parse_pipe_config import parse_pipe_config, parse_inline_config
from joule.utilities import timestamp_to_human

Loop = asyncio.AbstractEventLoop
Pipes = Dict[str, pipes.Pipe]
log = logging.getLogger('joule')

""" Create Numpy Pipes based for a module """


async def request_network_input(path: str, my_stream: stream.Stream, url: str,
                          pipe: pipes.Pipe, loop: Loop,
                          start_time: Optional[int] = None,
                          end_time: Optional[int] = None):
    # make sure the input is compatible
    my_node = node.Node(url)
    src_stream = await my_node.stream_get(path)
    if src_stream.layout != my_stream.layout:
        raise errors.ConfigurationError("Input [%s] configured for [%s] but source is [%s]" % (
            path, my_stream.layout, src_stream.layout))

    # if the input is *live* make sure the stream is being produced
    if not src_stream.is_destination and (start_time is None and end_time is None):
        raise errors.ConfigurationError("Input [%s] is not being produced, specify time bounds for historic execution" % path)
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
                    if pipe_in.end_of_interval:
                        await pipe_out.close_interval()
            except (asyncio.CancelledError, pipes.EmptyPipe):
                pass
            except aiohttp.ClientError as e:
                log.error("pipe_builders::_live_reader: %s" % str(e))
    await pipe_out.close()


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
                log.error("Error reading input [%s]: %s" % (my_stream.name, msg))
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
    my_node = node.Node(url)
    try:
        dest_stream = await my_node.stream_get(path)
        if start_time is not None or end_time is not None:
            await my_node.data_delete(dest_stream, start_time, end_time)

    except errors.StreamNotFound:
        dest_stream = await my_node.stream_create(my_stream, path)

    if dest_stream.layout != my_stream.layout:
        raise errors.ConfigurationError("Output [%s] configured for [%s] but destination is [%s]" % (
            path, my_stream.layout, dest_stream.layout))
    # raise a warning if the element names do not match
    actual_names = [e.name for e in dest_stream.elements]
    requested_names = [e.name for e in my_stream.elements]
    if actual_names != requested_names:  # pragma: no cover
        log.warning("[%s] elements do not match the existing stream" % path)

    # make sure the stream is not currently produced
    if dest_stream.is_destination:
        raise errors.ConfigurationError("Output [%s] is already being produced" % path)

    # all checks passed, subscribe to the output
    async def close():
        await task

    pipe = pipes.LocalPipe(dest_stream.layout, name=path, stream=dest_stream, close_cb=close)
    task = loop.create_task(my_node.data_write(dest_stream, pipe))
    return pipe
