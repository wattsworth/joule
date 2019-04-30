from typing import Union, Optional, List
import asyncio
import aiohttp
import numpy as np

from .session import BaseSession
from .stream import (Stream,
                     stream_get,
                     stream_create)

from joule.models.pipes import (Pipe,
                                InputPipe,
                                EmptyPipe,
                                LocalPipe,
                                interval_token)
from joule import errors

import logging

log = logging.getLogger('joule')


async def data_delete(session: BaseSession,
                      stream: Union[Stream, str, int],
                      start: Optional[int] = None,
                      end: Optional[int] = None):
    params = {}
    if start is not None:
        params['start'] = int(start)
    if end is not None:
        params['end'] = int(end)
    if type(stream) is Stream:
        params['id'] = stream.id
    elif type(stream) is str:
        params['path'] = stream
    elif type(stream) is int:
        params['id'] = stream
    else:
        raise errors.ApiError("Invalid stream datatype. Must be Stream, Path, or ID")

    await session.delete("/data", params)


async def data_write(session: BaseSession,
                     loop: asyncio.AbstractEventLoop,
                     stream: Union[Stream, str, int],
                     start_time: Optional[int] = None,
                     end_time: Optional[int] = None,
                     ) -> Pipe:
    # stream must exist, does not automatically create a stream
    # retrieve the destination stream object
    dest_stream = await stream_get(session, stream)
    if start_time is not None or end_time is not None:
        await data_delete(session, dest_stream, start_time, end_time)

    if type(stream) is Stream:
        if dest_stream.layout != stream.layout:
            raise errors.ApiError("Stream [%s] configured for [%s] but destination is [%s]" % (
                stream.name, stream.layout, dest_stream.layout))
        # raise a warning if the element names do not match
        actual_names = [e.name for e in dest_stream.elements]
        requested_names = [e.name for e in stream.elements]
        if actual_names != requested_names:  # pragma: no cover
            log.warning("[%s] elements do not match the existing stream" % stream.name)

    # make sure the stream is not currently produced
    if dest_stream.is_destination:
        raise errors.ApiError("Stream [%s] is already being produced" % dest_stream.name)

    # all checks passed, subscribe to the output
    async def close():
        await task

    pipe = LocalPipe(dest_stream.layout, name=dest_stream.name,
                     stream=dest_stream, close_cb=close)
    task = loop.create_task(_send_data(session, dest_stream, pipe))
    return pipe


async def data_intervals(session: BaseSession,
                         stream: Union[Stream, str, int],
                         start_time: Optional[int] = None,
                         end_time: Optional[int] = None,
                         ) -> List:
    data = {}
    if type(stream) is Stream:
        data["id"] = stream.id
    elif type(stream) is int:
        data["id"] = stream
    elif type(stream) is str:
        data["path"] = stream
    else:
        raise errors.ApiError("Invalid stream datatype. Must be Stream, Path, or ID")
    if start_time is not None:
        data['start'] = int(start_time)
    if end_time is not None:
        data['end'] = int(end_time)
    return await session.get("/data/intervals.json", params=data)


async def data_read(session: BaseSession,
                    loop: asyncio.AbstractEventLoop,
                    stream: Union[Stream, str, int],
                    start: Optional[int] = None,
                    end: Optional[int] = None,
                    max_rows: Optional[int] = None) -> Pipe:
    # make sure the input is compatible
    src_stream = await stream_get(session, stream)
    if type(stream) is Stream:
        if src_stream.layout != src_stream.layout:
            raise errors.ApiError("Input [%s] configured for [%s] but source is [%s]" % (
                stream, stream.layout, src_stream.layout))

    # replace the stub stream (from config file) with actual stream
    pipe = LocalPipe(src_stream.layout, name=src_stream.name, loop=loop, stream=src_stream)
    pipe.stream = src_stream
    task = loop.create_task(_historic_reader(session,
                                             src_stream,
                                             pipe,
                                             start, end, max_rows))

    async def close():
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    pipe.close_cb = close
    return pipe


async def data_subscribe(session: BaseSession,
                         loop: asyncio.AbstractEventLoop,
                         stream: Union[Stream, str, int]) -> Pipe:
    # make sure the input is compatible
    src_stream = await stream_get(session, stream)
    if type(stream) is Stream:
        if src_stream.layout != src_stream.layout:
            raise errors.ApiError("Input [%s] configured for [%s] but source is [%s]" % (
                stream, stream.layout, src_stream.layout))

    # make sure the stream is being produced
    if not src_stream.is_destination:
        raise errors.ApiError(
            "Stream [%s] is not being produced, specify time bounds for historic execution" % src_stream.name)
    # replace the stub stream (from config file) with actual stream
    pipe = LocalPipe(src_stream.layout, name=src_stream.name, loop=loop, stream=src_stream)
    pipe.stream = src_stream

    task = loop.create_task(_live_reader(session,
                                         src_stream,
                                         pipe))

    async def close():
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    pipe.close_cb = close
    return pipe


async def _live_reader(session: BaseSession, my_stream: Stream,
                       pipe_out: Pipe):
    log.info("requesting live connection to [%s]" % my_stream.name)
    params = {'id': my_stream.id, 'subscribe': '1'}
    try:
        raw_session = await session.get_session()
        async with raw_session.get(session.url + "/data",
                                   params=params,
                                   ssl=session.ssl_context) as response:
            if response.status != 200:  # pragma: no cover
                msg = await response.text()
                log.error("Error reading input [%s]: " % my_stream.name, msg)
                await pipe_out.close()
                return
            pipe_out.change_layout(response.headers['joule-layout'])
            pipe_out.decimation_level = int(response.headers['joule-decimation'])
            pipe_in = InputPipe(layout=pipe_out.layout,
                                stream=my_stream, reader=response.content)
            while True:
                data = await pipe_in.read()
                pipe_in.consume(len(data))
                await pipe_out.write(data)
                if pipe_in.end_of_interval:
                    await pipe_out.close_interval()

    except (asyncio.CancelledError, EmptyPipe, aiohttp.ClientError):
        pass
    except Exception as e:
        print("unexpected exception: ", e)
        raise e
    await pipe_out.close()


async def _historic_reader(session: BaseSession,
                           my_stream: Stream,
                           pipe_out: Pipe,
                           start_time: int, end_time: int,
                           max_rows: Optional[int]):
    log.info("requesting historic connection to [%s]" % my_stream.name)
    params = {'id': my_stream.id}
    if max_rows is not None:
        params['max-rows'] = max_rows
    if start_time is not None:
        params['start'] = int(start_time)
    if end_time is not None:
        params['end'] = int(end_time)
    try:
        my_session = await session.get_session()
        async with my_session.get(session.url + "/data",
                                  params=params,
                                  ssl=session.ssl_context) as response:
            if response.status != 200:  # pragma: no cover
                msg = await response.text()
                log.error("Error reading input [%s]: %s" % (my_stream.name, msg))
                await pipe_out.close()
                return
            pipe_out.change_layout(response.headers['joule-layout'])
            pipe_out.decimation_level = int(response.headers['joule-decimation'])
            pipe_in = InputPipe(layout=pipe_out.layout,
                                stream=my_stream, reader=response.content)
            while True:
                data = await pipe_in.read()
                pipe_in.consume(len(data))
                await pipe_out.write(data)
                if pipe_in.end_of_interval:
                    await pipe_out.close_interval()

    except (asyncio.CancelledError, EmptyPipe):
        pass
    except Exception as e:
        print("unexpected exception: ", e)
        raise e
    finally:
        await pipe_out.close()


async def _send_data(session: BaseSession,
                     stream: Stream,
                     pipe: Pipe):
    output_complete = False

    async def _data_sender():
        nonlocal output_complete
        try:
            while True:
                data = await pipe.read()
                if len(data) > 0:
                    yield data.tostring()
                if pipe.end_of_interval:
                    yield interval_token(stream.layout).tostring()
                pipe.consume(len(data))
        except EmptyPipe:
            pass
        output_complete = True

    while not output_complete:
        try:
            await session.post("/data",
                               params={"id": stream.id},
                               data=_data_sender())
        except errors.ApiError as e:  # pragma: no cover
            log.info("Error submitting data to joule [%s], retrying" % str(e))
