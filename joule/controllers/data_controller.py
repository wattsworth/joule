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
    try:
        for param in params:
            if param in request.query:
                params[param] = int(request.query[param])
    except ValueError as e:
        return web.Response(text="parameter [%s] must be an int" % e, status=400)

    # make sure parameters make sense
    if ((params['start'] is not None and params['end'] is not None) and
            (params['start'] >= params['end'])):
        return web.Response(text="[start] must be < [end]", status=400)
    if params['max-rows'] is not None and params['max-rows'] <= 0:
        return web.Response(text="[max-rows] must be > 0", status=400)
    if params['decimation-level'] is not None and params['decimation-level'] <= 0:
        return web.Response(text="[max-rows] must be > 0", status=400)

    # --- Binary Streaming Handler ---
    resp = None

    async def stream_data(data: np.ndarray, layout, decimated):
        nonlocal resp
        if resp is None:
            resp = web.StreamResponse(status=200,
                                      headers={'joule-layout': layout,
                                               'joule-decimated': str(decimated)})
            resp.enable_chunked_encoding()
            await resp.prepare(request)
        await resp.write(data.tostring())

    # --- JSON Handler ---

    data_blocks = []  # array of data segments
    data_segment = None
    is_decimated = False

    async def retrieve_data(data: np.ndarray, layout, decimated):
        nonlocal data_blocks, data_segment, is_decimated
        if decimated:
            is_decimated = True
        if np.array_equal(data, pipes.interval_token(layout)):
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
        extractor = await data_store.extract(stream, params['start'], params['end'],
                                             callback=callback,
                                             max_rows=params['max-rows'],
                                             decimation_level=params['decimation-level'])
        await extractor
    except InsufficientDecimationError as e:
        return web.Response(text="decimated data is not available: %s" % e, status=400)
    except DataError as e:
        return web.Response(text="read error: %s" % e, status=400)

    if json:
        return web.json_response({"data": data_blocks, "decimated": is_decimated})
    else:
        return resp


async def write(request):
    return web.Response(text="TODO")
