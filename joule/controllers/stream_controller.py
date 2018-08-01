from aiohttp import web
from sqlalchemy.orm import Session
from joule.models import Stream, DataStore, stream
import json

from joule.models import folder, ConfigurationError


async def index(request: web.Request):
    db: Session = request.app["db"]
    data_store: DataStore = request.app["data-store"]
    root = folder.root(db)
    streams = db.query(Stream).all()
    streams_info = await data_store.info(streams)
    resp = root.to_json(streams_info)
    return web.json_response(resp)


async def info(request: web.Request):
    db: Session = request.app["db"]
    data_store: DataStore = request.app["data-store"]
    if 'path' in request.query:
        my_stream = folder.find_stream_by_path(request.query['path'], db)
    elif 'id' in request.query:
        my_stream = db.query(Stream).get(request.query["id"])
    else:
        return web.Response(text="specify an id or a path", status=400)
    if my_stream is None:
        return web.Response(text="stream does not exist", status=404)
    stream_info = await data_store.info([my_stream])
    return web.json_response(my_stream.to_json(stream_info))


async def move(request: web.Request):
    db: Session = request.app["db"]
    body = await request.post()
    # find the stream
    if 'path' in body:
        my_stream = folder.find_stream_by_path(body['path'], db)
    elif 'id' in body:
        my_stream = db.query(Stream).get(body["id"])
    else:
        return web.Response(text="specify an id or a path", status=400)
    if my_stream is None:
        return web.Response(text="stream does not exist", status=404)
    # find or create the destination folder
    if 'destination' not in body:
        return web.Response(text="specify a destination", status=400)
    try:
        destination = folder.find_or_create(body['destination'], db)
    except ConfigurationError as e:
        return web.Response(text="Destination error: %s" % str(e), status=400)
    # make sure there are no other streams with the same name here
    for peer in destination.streams:
        if peer.name == my_stream.name:
            return web.Response(text="a stream with this name is in the destination folder",
                                status=400)
    destination.streams.append(my_stream)
    db.commit()
    return web.json_response({"stream": my_stream.to_json()})


async def create(request):
    db: Session = request.app["db"]
    body = await request.post()
    if 'path' not in body:
        return web.Response(text="specify a path", status=400)
    path = body['path']
    if 'stream' not in body:
        return web.Response(text="provide a stream", status=400)
    try:
        new_stream = stream.from_json(json.loads(body['stream']))
        # clear out the id's
        new_stream.id = None
        for elem in new_stream.elements:
            elem.id = None
        destination = folder.find_or_create(path, db)
        destination.streams.append(new_stream)
        db.commit()
    except ValueError as e:
        return web.Response(text="Invalid stream JSON: %r" % e, status=400)
    except (KeyError, ConfigurationError) as e:
        return web.Response(text="Invalid stream specification: %r" % e, status=400)
    return web.json_response(data=new_stream.to_json())


async def update(_):  # pragma: no cover
    return web.Response(text="TODO",
                        content_type='application/json')


async def delete(request):
    db: Session = request.app["db"]
    data_store: DataStore = request.app["data-store"]
    # find the requested stream
    if 'path' in request.query:
        my_stream = folder.find_stream_by_path(request.query['path'], db)
    elif 'id' in request.query:
        my_stream = db.query(Stream).get(request.query["id"])
    else:
        return web.Response(text="specify an id or a path", status=400)
    if my_stream is None:
        return web.Response(text="stream does not exist", status=404)
    await data_store.destroy(my_stream)
    db.delete(my_stream)
    db.commit()
    return web.Response(text="ok")
