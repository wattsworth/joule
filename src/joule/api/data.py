from typing import Union, Optional, List
import asyncio
import aiohttp
import numpy as np
from joule.models.pipes import compute_dtype
from joule.utilities.misc import timestamps_are_monotonic, validate_values
from .session import BaseSession
from .data_stream import (DataStream,
                          data_stream_get,
                          data_stream_create)

from joule.models.pipes import (Pipe,
                                InputPipe,
                                EmptyPipe,
                                PipeError,
                                LocalPipe,
                                interval_token)
from joule import errors

import logging

log = logging.getLogger('joule')


async def data_delete(session: BaseSession,
                      stream: Union[DataStream, str, int],
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
        raise errors.ApiError("Invalid stream datatype. Must be DataStream, Path, or ID")

    await session.delete("/data", params)


async def data_write(session: BaseSession,
                     stream: Union[DataStream, str, int],
                     start_time: Optional[int] = None,
                     end_time: Optional[int] = None,
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
        if actual_names != requested_names:  # pragma: no cover
            log.warning("[%s] elements do not match the existing stream" % stream.name)

    # make sure the stream is not currently produced
    if dest_stream.is_destination:
        raise errors.ApiError("DataStream [%s] is already being produced" % dest_stream.name)

    # all checks passed, subscribe to the output
    async def close():
        await task

    pipe = LocalPipe(dest_stream.layout, name=dest_stream.name,
                     stream=dest_stream, close_cb=close, debug=False, write_limit=5)
    task = asyncio.create_task(_send_data(session, dest_stream, pipe))
    return pipe


async def data_intervals(session: BaseSession,
                         stream: Union[DataStream, str, int],
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
        raise errors.ApiError("Invalid stream datatype. Must be DataStream, Path, or ID")
    if start_time is not None:
        data['start'] = int(start_time)
    if end_time is not None:
        data['end'] = int(end_time)
    return await session.get("/data/intervals.json", params=data)

async def data_drop_decimations(session: BaseSession,
                                stream: Union[DataStream, str, int]):
    data = {}
    if type(stream) is DataStream:
        data["id"] = stream.id
    elif type(stream) is int:
        data["id"] = stream
    elif type(stream) is str:
        data["path"] = stream
    else:
        raise errors.ApiError("Invalid stream datatype. Must be DataStream, Path, or ID")
    await session.delete("/data/decimate.json", params=data)


async def data_decimate(session: BaseSession,
                                stream: Union[DataStream, str, int]):
    data = {}
    if type(stream) is DataStream:
        data["id"] = stream.id
    elif type(stream) is int:
        data["id"] = stream
    elif type(stream) is str:
        data["path"] = stream
    else:
        raise errors.ApiError("Invalid stream datatype. Must be DataStream, Path, or ID")
    await session.post("/data/decimate.json", params=data)


async def data_consolidate(session: BaseSession,
                           stream: Union[DataStream, str, int],
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
        raise errors.ApiError("Invalid stream datatype. Must be DataStream, Path, or ID")
    if start_time is not None:
        data['start'] = int(start_time)
    if end_time is not None:
        data['end'] = int(end_time)
    data['max_gap'] = int(max_gap)
    resp = await session.post("/data/consolidate.json", params=data)
    return resp['num_consolidated']


async def data_read(session: BaseSession,
                    stream: Union[DataStream, str, int],
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


async def data_read_array(session: BaseSession,
                          stream: Union[DataStream, str, int],
                          start: Optional[int] = None,
                          end: Optional[int] = None,
                          max_rows: int = 10000,
                          flatten: bool = False) -> np.ndarray:
    """ Read the requested data into a numpy array, raises ValueError
    if the stream has more data than max_rows"""
    if type(stream) is not DataStream:
        stream = await data_stream_get(session, stream)
    # check if the data can be retrieved directly from NilmDB
    if await session.is_nilmdb_available():
        return await _read_nilmdb_data(session.nilmdb_url, stream, start, end, max_rows, flatten)
    else:
        pipe = await data_read(session, stream, start, end, max_rows)
        return await pipe.read_all(flatten=flatten)



async def data_subscribe(session: BaseSession,
                         stream: Union[DataStream, str, int]) -> Pipe:
    # make sure the input is compatible
    src_stream = await data_stream_get(session, stream)
    if type(stream) is DataStream:
        if src_stream.layout != src_stream.layout:
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
        async with raw_session.get(session.url + "/data",
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

    except (asyncio.CancelledError, EmptyPipe, aiohttp.ClientError, PipeError):
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
        async with my_session.get(session.url + "/data",
                                  params=params,
                                  ssl=session.ssl_context) as response:
            if response.status != 200:  # pragma: no cover
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
                     stream: DataStream,
                     pipe: Pipe):
    # TODO is this necssary?
    output_complete = False

    async def _data_sender():
        nonlocal output_complete
        try:
            last_ts = None
            while True:
                data = await pipe.read()
                if not timestamps_are_monotonic(data,last_ts,stream.name):
                    raise errors.ApiError("timestamps are not monotonic")
                if not validate_values(data):
                    raise errors.ApiError("invalid values (NaN or Inf)")
                last_ts = data['timestamp'][-1]
                if len(data) > 0:
                    yield data.tobytes()
                if pipe.end_of_interval:
                    yield interval_token(stream.layout).tobytes()
                pipe.consume(len(data))
        except EmptyPipe:
            yield interval_token(stream.layout).tobytes()
        output_complete = True

    try:
        result = await session.post("/data",
                                    params={"id": stream.id},
                                    data=_data_sender(),
                                    chunked=True)
    except Exception as e:
        pipe.fail()
        raise e

async def _read_nilmdb_data(nilmdb_url, stream, start, end, max_rows, flatten) -> np.ndarray:
    url = f"{nilmdb_url}/stream/extract"
    params = {"path": f"/joule/{stream.id}",
              "binary": 1,
              "start": start,
              "end": end}
    dtype = compute_dtype(stream.layout)
    max_bytes = max_rows * dtype.itemsize

    data = b''
    async with aiohttp.ClientSession() as session:
        async with session.get(url, params=params) as resp:
            while not resp.content.at_eof() and len(data)<=max_bytes:
                data += await resp.content.read(max_bytes)
            if not resp.content.at_eof():
                print(f"WARNING: Requested time interval mas more data than {max_rows} rows of data")
    sdata = np.frombuffer(data[:max_bytes], dtype=dtype)
    if flatten:
        return np.c_[sdata['timestamp'][:, None], sdata['data']]
    else:
        return sdata
