from aiohttp import web
from sqlalchemy.orm import Session
from joule.models import Stream, DataStore, stream
import json

from joule.models import folder, Folder
from joule.errors import ConfigurationError


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
    if request.content_type != 'application/json':
        return web.Response(text='content-type must be application/json', status=400)
    body = await request.json()
    # find the stream
    if 'src_path' in body:
        my_stream = folder.find_stream_by_path(body['src_path'], db)
    elif 'src_id' in body:
        my_stream = db.query(Stream).get(body["src_id"])
    else:
        return web.Response(text="specify a source id or a path", status=400)
    if my_stream is None:
        return web.Response(text="stream does not exist", status=404)
    if my_stream.locked:
        return web.Response(text="locked streams cannot be moved", status=400)
    # find or create the destination folder
    if 'dest_path' in body:
        try:
            destination = folder.find(body['dest_path'], db, create=True)
        except ConfigurationError as e:
            return web.Response(text="Destination error: %s" % str(e), status=400)
    elif 'dest_id' in body:
        destination = db.query(Folder).get(body["dest_id"])
    else:
        return web.Response(text="specify a destination", status=400)
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
    if request.content_type != 'application/json':
        return web.Response(text='content-type must be application/json', status=400)
    body = await request.json()

    if 'stream' not in body:
        return web.Response(text="provide a stream", status=400)

    # find or create the destination folder
    if 'dest_path' in body:
        try:
            destination = folder.find(body['dest_path'], db, create=True)
        except ConfigurationError as e:
            return web.Response(text="Destination error: %s" % str(e), status=400)
    elif 'dest_id' in body:
        destination = db.query(Folder).get(body["dest_id"])
    else:
        return web.Response(text="specify a destination", status=400)

    try:
        new_stream = stream.from_json(body['stream'])
        # clear out the status flags
        new_stream.is_configured = False
        new_stream.is_destination = False
        new_stream.is_source = False
        # clear out the id's
        new_stream.id = None
        for elem in new_stream.elements:
            elem.id = None
        destination.streams.append(new_stream)
        db.commit()
    except ValueError as e:
        db.rollback()
        return web.Response(text="Invalid stream JSON: %r" % e, status=400)
    except (KeyError, ConfigurationError) as e:
        db.rollback()
        return web.Response(text="Invalid stream specification: %r" % e, status=400)
    return web.json_response(data=new_stream.to_json())


async def update(request: web.Request):
    db: Session = request.app["db"]
    body = await request.post()  # request.json?
    if 'id' not in body:
        return web.Response(text="Invalid request: specify id", status=400)

    my_stream: Stream = db.query(Stream).get(body['id'])
    if my_stream is None:
        return web.Response(text="stream does not exist", status=404)
    if my_stream.locked:
        return web.Response(text="stream is locked", status=400)
    if 'stream' not in body:
        return web.Response(text="Invalid request: specify stream as JSON", status=400)
    try:
        attrs = json.loads(body['stream'])
    except ValueError:
        return web.Response(text="error: [stream] attribute must be JSON", status=400)
    try:
        my_stream.update_attributes(attrs)
        db.commit()
    except (ValueError, ConfigurationError) as e:
        db.rollback()
        return web.Response(text="error: %s" % e, status=400)
    return web.json_response(data=my_stream.to_json())


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
    if my_stream.locked or my_stream.active:
        return web.Response(text="locked streams cannot be deleted", status=400)
    await data_store.destroy(my_stream)
    db.delete(my_stream)
    db.commit()
    return web.Response(text="ok")
