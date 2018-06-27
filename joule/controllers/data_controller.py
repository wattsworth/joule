from sqlalchemy.orm import Session
from aiohttp import web
import numpy as np
import asyncio
import pdb

from joule.models import folder, DataStore, Stream, InsufficientDecimationError


async def read(request: web.Request):
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

    # create an extraction task
    q = asyncio.Queue()
    try:
        task = data_store.extract(stream, params['start'], params['end'], q,
                                  max_rows=params['max-rows'],
                                  decimation_level=params['decimation-level'])
    except InsufficientDecimationError as e:
        return web.Response(text="decimated data is not available: %s" % e)
    extractor = request.loop.create_task(task)

    # send data in chunks
    resp = web.StreamResponse(status=200)
    resp.enable_chunked_encoding()
    await resp.prepare(request)
    while True:
        data: np.array = await q.get()
        await resp.write(data.tostring())
        if extractor.done() and q.empty():
            break
    await extractor
    return resp


async def write(request):
    return web.Response(text="TODO")
