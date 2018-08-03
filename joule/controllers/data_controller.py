from sqlalchemy.orm import Session
from aiohttp import web
import numpy as np
import asyncio
import pdb

from joule.models import folder, DataStore, Stream, InsufficientDecimationError, DataError
from joule.models import pipes


async def read_json(request: web.Request):
    return await read(request, json=True)


async def read(request: web.Request, json=False):
    db: Session = request.app["db"]
    data_store: DataStore = request.app["data-store"]
    # find the requested stream
    if 'path' in request.query:
        stream = folder.find_stream_by_path(request.query['path'], db)
    elif 'id' in request.query:
        stream = db.query(Stream).get(request.query["id"])
    else:
        return web.Response(text="specify an id or a path", status=400)
    if stream is None:
        return web.Response(text="stream does not exist", status=404)

    # parse optional parameters
    params = {'start': None, 'end': None, 'max-rows': None, 'decimation-level': None}
    param = ""  # to appease type checker
    try:
        for param in params:
            if param in request.query:
                params[param] = int(request.query[param])
    except ValueError:
        return web.Response(text="parameter [%s] must be an int" % param, status=400)

    # make sure parameters make sense
    if ((params['start'] is not None and params['end'] is not None) and
            (params['start'] >= params['end'])):
        return web.Response(text="[start] must be < [end]", status=400)
    if params['max-rows'] is not None and params['max-rows'] <= 0:
        return web.Response(text="[max-rows] must be > 0", status=400)
    if params['decimation-level'] is not None and params['decimation-level'] <= 0:
        return web.Response(text="[decimation-level] must be > 0", status=400)

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
        await resp.write(data.tostring())

    # --- JSON Handler ---

    data_blocks = []  # array of data segments
    data_segment = None
    decimation_factor = 1

    async def retrieve_data(data: np.ndarray, layout, factor):
        nonlocal data_blocks, data_segment, decimation_factor
        decimation_factor = factor
        if np.array_equal(data, pipes.interval_token(layout)):
            if data_segment is not None:
                data_blocks.append(data_segment.tolist())
                data_segment = None
        else:
            data = np.c_[data['timestamp'][:, None], data['data']]
            if data_segment is None:
                data_segment = data
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
        return web.Response(text="decimated data is not available: %s" % e, status=400)
    except DataError as e:
        return web.Response(text="read error: %s" % e, status=400)

    if json:
        # put the last data_segment on
        if data_segment is not None:
            data_blocks.append(data_segment.tolist())
        return web.json_response({"data": data_blocks, "decimation_factor": decimation_factor})
    else:
        return resp


async def intervals(request: web.Request):
    db: Session = request.app["db"]
    data_store: DataStore = request.app["data-store"]
    # find the requested stream
    if 'path' in request.query:
        stream = folder.find_stream_by_path(request.query['path'], db)
    elif 'id' in request.query:
        stream = db.query(Stream).get(request.query["id"])
    else:
        return web.Response(text="specify an id or a path", status=400)
    if stream is None:
        return web.Response(text="stream does not exist", status=404)
    # parse time bounds if specified
    try:
        if 'start' in request.query:
            start = int(request.query['start'])
        else:
            start = None
        if 'end' in request.query:
            end = int(request.query['end'])
        else:
            end = None
    except ValueError:
        return web.Response(text="[start] and [end] must be an integers", status=400)

    # make sure parameters make sense
    if (start is not None and end is not None) and start >= end:
        return web.Response(text="[start] must be < [end]", status=400)

    return web.json_response(await data_store.intervals(stream, start, end))


async def write(request: web.Request):
    db: Session = request.app["db"]
    data_store: DataStore = request.app["data-store"]
    # find the requested stream
    if 'path' in request.query:
        stream = folder.find_stream_by_path(request.query['path'], db)
    elif 'id' in request.query:
        stream = db.query(Stream).get(request.query["id"])
    else:
        return web.Response(text="specify an id or a path", status=400)
    if stream is None:
        return web.Response(text="stream does not exist", status=404)
    # spawn in inserter task
    pipe = pipes.InputPipe(name="inbound", stream=stream, reader=request.content)
    task = data_store.spawn_inserter(stream, pipe, request.loop, insert_period=0)
    await task
    return web.Response(text="ok")


async def remove(request: web.Request):
    db: Session = request.app["db"]
    data_store: DataStore = request.app["data-store"]
    # find the requested stream
    if 'path' in request.query:
        stream = folder.find_stream_by_path(request.query['path'], db)
    elif 'id' in request.query:
        stream = db.query(Stream).get(request.query["id"])
    else:
        return web.Response(text="specify an id or a path", status=400)
    if stream is None:
        return web.Response(text="stream does not exist", status=404)

    # parse time bounds
    start = None
    end = None
    try:
        if 'start' in request.query:
            start = int(request.query['start'])
        if 'end' in request.query:
            end = int(request.query['end'])
    except ValueError:
        return web.Response(text="[start] and [end] must be integers", status=400)

    # make sure bounds make sense
    if ((start is not None and end is not None) and
            (start >= end)):
        return web.Response(text="[start] must be < [end]", status=400)

    await data_store.remove(stream, start, end)
    return web.Response(text="ok")
