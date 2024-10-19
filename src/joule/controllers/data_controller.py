from sqlalchemy.orm import Session
from aiohttp import web
import numpy as np
import asyncio
import logging
from joule import app_keys

from joule.models import (folder, DataStore, DataStream,
                          InsufficientDecimationError, DataError,
                          pipes)
from joule.models.supervisor import Supervisor
from joule.constants import ApiErrorMessages
from joule.errors import SubscriptionError
from joule.controllers.helpers import validate_query_parameters, get_stream_from_request_params
log = logging.getLogger('joule')


async def read_json(request: web.Request):
    return await read(request, json=True)


async def read(request: web.Request, json=False):
    if 'subscribe' in request.query and request.query['subscribe'] == '1':
        return await _subscribe(request, json)
    else:
        return await _read(request, json)


async def _read(request: web.Request, json):
    db: Session = request.app[app_keys.db]
    data_store: DataStore = request.app[app_keys.data_store]
    stream = get_stream_from_request_params(request, db)
    
    # parse optional parameters
    params = {'start': None, 'end': None, 'max-rows': None, 'decimation-level': None}
    validate_query_parameters(params, request.query)
    # additional parameter checks
    if params['max-rows'] is not None and params['max-rows'] <= 0:
        raise web.HTTPBadRequest(reason="[max-rows] must be > 0")
    if params['decimation-level'] is not None and params['decimation-level'] <= 0:
        raise web.HTTPBadRequest(reason="[decimation-level] must be > 0")

    # --- Binary Streaming Handler ---
    resp = None

    async def stream_data(data: np.ndarray, layout, factor):
        nonlocal resp

        if resp is None:
            resp = web.StreamResponse(status=200,
                                      headers={'joule-layout': layout,
                                               'joule-decimation': str(factor)})
            resp.enable_chunked_encoding()
            await resp.prepare(request)
        await resp.write(data.tobytes())

    # --- JSON Handler ---

    data_blocks = []  # array of data segments
    data_segment = None
    decimation_factor = 1

    async def retrieve_data(data: np.ndarray, layout, factor):
        nonlocal data_blocks, data_segment, decimation_factor
        decimation_factor = factor
        ## CASE 1: Interval token by itself, no data
        if np.array_equal(data, pipes.interval_token(layout)):
            if data_segment is not None:
                data_blocks.append(data_segment.tolist())
                data_segment = None
        ## CASE 2: Data followed by an interval token
        elif len(data)>0 and np.array_equal([data[-1]],pipes.interval_token(layout)):
            # flatten the structured array
            data = np.c_[data['timestamp'][:, None], data['data']]
            # remove the interval token
            data = data[:-1,:]
            # CASE 2.1: Last segment of data from the interval (we already have part of it)
            if data_segment is not None:
                data_segment = np.vstack((data_segment, data))
                data_blocks.append(data_segment.tolist())
                data_segment = None
            # CASE 2.2: This chunk of data is the entire interval (no existing data from this interval)
            elif len(data)>0: 
                # only need to create a data block if there's actually data in this segment
                data_blocks.append(data.tolist())
        ## CASE 3: Just data- no interval token
        else:
            data = np.c_[data['timestamp'][:, None], data['data']]
            ## CASE 3.1: First segment of data from a new interval
            if data_segment is None:
                data_segment = data
            ## CASE 3.2: Subsequent segments of data from the same interval
            else:
                data_segment = np.vstack((data_segment, data))

    if json:
        callback = retrieve_data
    else:
        callback = stream_data

    # create an extraction task
    try:
        await data_store.extract(stream, params['start'], params['end'],
                                 callback=callback,
                                 max_rows=params['max-rows'],
                                 decimation_level=params['decimation-level'])
    except InsufficientDecimationError as e:
        raise web.HTTPBadRequest(reason="decimated data is not available: %s" % e)
    except DataError as e:
        raise web.HTTPBadRequest(reason=f"read error: {str(e)}")

    if json:
        # put the last data_segment on
        if data_segment is not None:
            data_blocks.append(data_segment.tolist())
        return web.json_response({"data": data_blocks, "decimation_factor": decimation_factor})
    else:
        if resp is None:
            return web.json_response(text="this stream has no data", status=400)
        return resp


async def _subscribe(request: web.Request, json: bool):
    db: Session = request.app[app_keys.db]
    supervisor: Supervisor = request.app[app_keys.supervisor]
    if json:
        raise web.HTTPBadRequest(reason="JSON subscription not implemented")
    stream = get_stream_from_request_params(request, db)
    pipe = pipes.LocalPipe(stream.layout)
    try:
        unsubscribe = supervisor.subscribe(stream, pipe)
    except SubscriptionError:
        raise web.HTTPBadRequest(reason="stream is not being produced")
    resp = web.StreamResponse(status=200,
                              headers={'joule-layout': stream.layout,
                                       'joule-decimation': '1'})
    resp.enable_chunked_encoding()

    try:
        await resp.prepare(request)
        while await pipe.not_empty():
            data = await pipe.read()
            pipe.consume(len(data))
            if len(data) > 0:
                await resp.write(data.tobytes())
            if pipe.end_of_interval:
                await resp.write(pipes.interval_token(stream.layout).tobytes())
    except ConnectionResetError:
        pass # ignore client disconnect
    finally:
        unsubscribe()
    return resp

async def intervals(request: web.Request):
    db: Session = request.app[app_keys.db]
    data_store: DataStore = request.app[app_keys.data_store]
    stream = get_stream_from_request_params(request, db)
    params = {'start': None, 'end': None}
    validate_query_parameters(params, request.query)

    return web.json_response(await data_store.intervals(stream, params['start'], params['end']))


async def write(request: web.Request):
    db: Session = request.app[app_keys.db]
    data_store: DataStore = request.app[app_keys.data_store]
    stream = get_stream_from_request_params(request, db)
    # spawn in inserter task
    stream.is_destination = True
    db.commit()

    pipe = pipes.InputPipe(name="inbound", stream=stream, reader=request.content)
    if 'merge-gap' in request.query:
        try:
            merge_gap = int(request.query['merge-gap'])
        except ValueError:
            raise web.HTTPBadRequest(reason="merge-gap must be an integer")
        
        if merge_gap < 0:
            raise web.HTTPBadRequest(reason="merge-gap must be >= 0")
    else:
        merge_gap = 0
    try:
        task = await data_store.spawn_inserter(stream, pipe, insert_period=0, merge_gap=merge_gap)
        await task
    # ConnectionError is raised when the client disconnects unexpectedly which can happen often (module stops, etc)
    except (DataError, ConnectionError) as e:
        stream.is_destination = False
        db.commit()
        raise web.HTTPBadRequest(reason=str(e))
    finally:
        stream.is_destination = False
        db.commit()
    return web.Response(text="ok")


async def remove(request: web.Request):
    db: Session = request.app[app_keys.db]
    data_store: DataStore = request.app[app_keys.data_store]
    stream = get_stream_from_request_params(request, db)

    params = {'start': None, 'end': None}
    validate_query_parameters(params, request.query)

    await data_store.remove(stream, params['start'], params['end'])
    return web.Response(text="ok")


async def consolidate(request):
    db: Session = request.app[app_keys.db]
    data_store: DataStore = request.app[app_keys.data_store]
    _validate_support(data_store)

    stream = get_stream_from_request_params(request, db)
    params = {'start': None, 'end': None}
    validate_query_parameters(params, request.query)
    
    # parse the max_gap parameter
    if 'max_gap' not in request.query:
        raise web.HTTPBadRequest(reason="specify max_gap as us integer")
    try:
        max_gap = int(request.query['max_gap'])
        if max_gap <= 0:
            raise ValueError()
    except ValueError:
        raise web.HTTPBadRequest(reason="max_gap must be postive integer")
    num_removed = await data_store.consolidate(stream, params['start'], params['end'], max_gap)
    return web.json_response(data={"num_consolidated": num_removed})


async def decimate(request):
    db: Session = request.app[app_keys.db]
    data_store: DataStore = request.app[app_keys.data_store]
    stream = get_stream_from_request_params(request, db)
    _validate_support(data_store)
    await data_store.decimate(stream)
    return web.Response(text="ok")

async def drop_decimations(request):
    db: Session = request.app[app_keys.db]
    data_store: DataStore = request.app[app_keys.data_store]
    _validate_support(data_store)
    stream = get_stream_from_request_params(request, db)
    await data_store.drop_decimations(stream)
    return web.Response(text="ok")

### Helper Functions ###



def _validate_support(data_store: DataStore):
    # TimeScale supports decimation management (others may not)
    if not data_store.supports_decimation_management:
        raise web.HTTPBadRequest(reason="data store does not support decimation")