from typing import Optional, List, TYPE_CHECKING
import asyncio
import aiohttp
from joule.models.pipes import compute_dtype
from joule.utilities.time import time_now
from joule.utilities.validators import validate_monotonic_timestamps
from joule.utilities.validators import validate_no_nan_values
from joule.constants import EndPoints
from .session import BaseSession
from .data_stream import (DataStream,
                          data_stream_get)

from joule.models.pipes import (Pipe,
                                InputPipe,
                                LocalPipe,
                                interval_token)
from joule.errors import PipeError
from joule import errors

if TYPE_CHECKING:
    import numpy as np

import logging

log = logging.getLogger('joule')


async def data_delete(session: BaseSession,
                      stream: DataStream | str | int,
                      start: Optional[int] = None,
                      end: Optional[int] = None):
    params = {}
    if start is not None:
        params['start'] = int(start)
    if end is not None:
        params['end'] = int(end)
    if type(stream) is DataStream:
        params['id'] = stream.id
    elif type(stream) is str:
        params['path'] = stream
    elif type(stream) is int:
        params['id'] = stream
    else:
        raise errors.InvalidDataStreamParameter()

    await session.delete(EndPoints.data, params)


async def data_write(session: BaseSession,
                     stream: DataStream | str | int,
                     start_time: Optional[int] = None,
                     end_time: Optional[int] = None,
                     merge_gap: int = 0
                     ) -> Pipe:
    # stream must exist, does not automatically create a stream
    # retrieve the destination stream object
    dest_stream = await data_stream_get(session, stream)
    if start_time is not None or end_time is not None:
        await data_delete(session, dest_stream, start_time, end_time)

    if type(stream) is DataStream:
        if dest_stream.layout != stream.layout:
            raise errors.ApiError("DataStream [%s] configured for [%s] but destination is [%s]" % (
                stream.name, stream.layout, dest_stream.layout))
        # raise a warning if the element names do not match
        actual_names = [e.name for e in dest_stream.elements]
        requested_names = [e.name for e in stream.elements]
        if actual_names != requested_names:
            log.warning("[%s] elements do not match the existing stream" % stream.name)

    # make sure the stream is not currently produced
    if dest_stream.is_destination:
        raise errors.ApiError("DataStream [%s] is already being produced" % dest_stream.name)

    # all checks passed, subscribe to the output
    async def close():
        await task

    pipe = LocalPipe(dest_stream.layout, name=dest_stream.name,
                     stream=dest_stream, close_cb=close, debug=False, write_limit=5)
    task = asyncio.create_task(_send_data(session, dest_stream, pipe, merge_gap))
    return pipe


async def data_intervals(session: BaseSession,
                         stream: DataStream | str | int,
                         start_time: Optional[int] = None,
                         end_time: Optional[int] = None,
                         ) -> List:
    data = {}
    if type(stream) is DataStream:
        data["id"] = stream.id
    elif type(stream) is int:
        data["id"] = stream
    elif type(stream) is str:
        data["path"] = stream
    else:
        raise errors.InvalidDataStreamParameter()
    if start_time is not None:
        data['start'] = int(start_time)
    if end_time is not None:
        data['end'] = int(end_time)
    return await session.get(EndPoints.data_intervals, params=data)

async def data_drop_decimations(session: BaseSession,
                                stream: DataStream | str | int):
    data = {}
    if type(stream) is DataStream:
        data["id"] = stream.id
    elif type(stream) is int:
        data["id"] = stream
    elif type(stream) is str:
        data["path"] = stream
    else:
        raise errors.InvalidDataStreamParameter()
    await session.delete(EndPoints.data_decimate, params=data)


async def data_decimate(session: BaseSession,
                                stream: DataStream | str | int):
    data = {}
    if type(stream) is DataStream:
        data["id"] = stream.id
    elif type(stream) is int:
        data["id"] = stream
    elif type(stream) is str:
        data["path"] = stream
    else:
        raise errors.InvalidDataStreamParameter()
    await session.post(EndPoints.data_decimate, params=data)


async def data_consolidate(session: BaseSession,
                           stream: DataStream | str | int,
                           start_time: Optional[int] = None,
                           end_time: Optional[int] = None,
                           max_gap: int = 2e6
                           ) -> List:
    data = {}
    if type(stream) is DataStream:
        data["id"] = stream.id
    elif type(stream) is int:
        data["id"] = stream
    elif type(stream) is str:
        data["path"] = stream
    else:
        raise errors.InvalidDataStreamParameter()
    if start_time is not None:
        data['start'] = int(start_time)
    if end_time is not None:
        data['end'] = int(end_time)
    data['max_gap'] = int(max_gap)
    resp = await session.post(EndPoints.data_consolidate, params=data)
    return resp['num_consolidated']


async def data_read(session: BaseSession,
                    stream: DataStream | str | int,
                    start: Optional[int] = None,
                    end: Optional[int] = None,
                    max_rows: Optional[int] = None) -> Pipe:
    # make sure the input is compatible
    if type(stream) is not DataStream:
        stream = await data_stream_get(session, stream)
    # if type(stream) is DataStream:
    #    if src_stream.layout != src_stream.layout:
    #        raise errors.ApiError("Input [%s] configured for [%s] but source is [%s]" % (
    #            stream, stream.layout, src_stream.layout))
    # replace the stub stream (from config file) with actual stream
    pipe = LocalPipe(stream.layout, name=stream.name, stream=stream, write_limit=5)
    pipe.TIMEOUT_INTERVAL = 0.01 # read as fast as possible, any lower than this seems to cause race conditions in the pipes
    task = asyncio.create_task(_historic_reader(session,
                                                stream,
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
                         stream: DataStream | str | int) -> Pipe:
    # make sure the input is compatible
    src_stream = await data_stream_get(session, stream)
    if type(stream) is DataStream and stream.layout != src_stream.layout:
        raise errors.ApiError("Input [%s] configured for [%s] but source is [%s]" % (
            stream, stream.layout, src_stream.layout))

    # make sure the stream is being produced
    if not src_stream.is_destination:
        raise errors.ApiError(
            "DataStream [%s] is not being produced, specify time bounds for historic execution" % src_stream.name)
    # replace the stub stream (from config file) with actual stream
    # do not let the buffer grow beyond 5 server chunks
    pipe = LocalPipe(src_stream.layout, name=src_stream.name, stream=src_stream, write_limit=5)
    pipe.stream = src_stream

    task = asyncio.create_task(_live_reader(session,
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


async def _live_reader(session: BaseSession, my_stream: DataStream,
                       pipe_out: Pipe):
    log.info("requesting live connection to [%s]" % my_stream.name)
    params = {'id': my_stream.id, 'subscribe': '1'}
    try:
        raw_session = await session.get_session()
        async with raw_session.get(session.url + EndPoints.data,
                                   params=params,
                                   ssl=session.ssl_context) as response:
            if response.status != 200:
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

    except (asyncio.CancelledError, PipeError, aiohttp.ClientError):
        pass
    except Exception as e:
        print("unexpected exception: ", e)
        raise e
    await pipe_out.close()


async def _historic_reader(session: BaseSession,
                           my_stream: DataStream,
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
        async with my_session.get(session.url + EndPoints.data,
                                  params=params,
                                  ssl=session.ssl_context) as response:
            if response.status != 200:
                msg = await response.text()
                log.error("Error reading input [%s]: %s" % (my_stream.name, msg))
                await pipe_out.close()
                return
            # Suppress this message since it interferes with command line tools
            #print(f"WARNING: data pipe layout is incorrect, adjusting to {response.headers['joule-layout']}")
            pipe_out.change_layout(response.headers['joule-layout'])
            pipe_out.decimation_level = int(response.headers['joule-decimation'])
            pipe_in = InputPipe(layout=pipe_out.layout,
                                stream=my_stream, reader=response.content)
            while await pipe_in.not_empty():
                data = await pipe_in.read()
                pipe_in.consume(len(data))
                try:
                    await pipe_out.write(data)
                    if pipe_in.end_of_interval:
                        await pipe_out.close_interval()
                except PipeError as e:
                    if "closed pipe" in str(e):
                        # pipe was closed by the user, they don't want any more data
                        break
                    else:
                        raise e # something else happened, propogate the error
    except asyncio.CancelledError:
        pass
    finally:
        await pipe_out.close()


async def _send_data(session: BaseSession,
                     stream: DataStream,
                     pipe: Pipe,
                     merge_gap: int):

    async def _data_sender():
        last_ts = None
        while await pipe.not_empty():
            data = await pipe.read()
            if not validate_monotonic_timestamps(data,last_ts,stream.name):
                raise errors.ApiError("timestamps are not monotonic")
            if not validate_no_nan_values(data):
                raise errors.ApiError("invalid values (NaN or Inf)")
            if len(data) > 0:
                yield data.tobytes()
                last_ts = data['timestamp'][-1]
                # warn if there is data in this chunk that is older than the keep value
                # of the destination stream (-1 == KEEP ALL data)
                if stream.keep_us != -1 and (data['timestamp'][0] < time_now() - stream.keep_us):
                    log.warning("this data is older than the keep value of the destination stream, it may be discarded")
            if pipe.end_of_interval:
                yield interval_token(stream.layout).tobytes()
            pipe.consume(len(data))
        yield interval_token(stream.layout).tobytes()

    try:
        await session.post(EndPoints.data,
                           params={"id": stream.id, "merge-gap": int(merge_gap)},
                           data=_data_sender(),
                           chunked=True)
    except Exception as e:
        pipe.fail()
        raise e
