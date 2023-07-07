import datetime

from aiohttp import web
from sqlalchemy.orm import Session
from joule.models import (
    DataStream,
    EventStream,
    DataStore,
    data_stream)

from joule.models import folder, Folder
from joule.errors import ConfigurationError


async def info(request: web.Request):
    db: Session = request.app["db"]
    data_store: DataStore = request.app["data-store"]
    if 'path' in request.query:
        my_stream = folder.find_stream_by_path(request.query['path'], db, stream_type=DataStream)
    elif 'id' in request.query:
        my_stream = db.get(DataStream, request.query["id"])
    else:
        return web.Response(text="specify an id or a path", status=400)
    if my_stream is None:
        return web.Response(text="stream does not exist", status=404)
    if "no-info" in request.query:
        stream_info = None
    else:
        stream_info = await data_store.info([my_stream])
    return web.json_response(my_stream.to_json(stream_info))


async def move(request: web.Request):
    db: Session = request.app["db"]
    if request.content_type != 'application/json':
        return web.Response(text='content-type must be application/json', status=400)
    body = await request.json()
    # find the stream
    if 'src_path' in body:
        my_stream = folder.find_stream_by_path(body['src_path'], db, stream_type=DataStream)
    elif 'src_id' in body:
        my_stream = db.get(DataStream, body["src_id"])
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
        destination = db.get(Folder, body["dest_id"])
    else:
        return web.Response(text="specify a destination", status=400)
    # make sure name is unique in this destination
    existing_names = [s.name for s in destination.data_streams + destination.event_streams]
    if my_stream.name in existing_names:
        db.rollback()
        return web.Response(text="stream with the same name exists in the destination folder",
                            status=400)
    my_stream.touch()
    destination.data_streams.append(my_stream)
    destination.touch()
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
        destination = db.get(Folder, body["dest_id"])
    else:
        return web.Response(text="specify a destination", status=400)

    try:
        new_stream = data_stream.from_json(body['stream'])
        # make sure stream has at least 1 element
        if len(new_stream.elements) == 0:
            raise ConfigurationError("stream must have at least one element")

        # clear out the status flags
        new_stream.is_configured = False
        new_stream.is_destination = False
        new_stream.is_source = False
        # make sure element names are unique
        element_names = [e.name for e in new_stream.elements]
        if len(set(element_names)) != len(element_names):
            raise ConfigurationError("element names must be unique")
        # clear out the id's
        new_stream.id = None
        for elem in new_stream.elements:
            elem.id = None
        # make sure name is unique in this destination
        existing_names = [s.name for s in destination.data_streams + destination.event_streams]
        if new_stream.name in existing_names:
            raise ConfigurationError("stream with the same name exists in the folder")
        destination.data_streams.append(new_stream)
        new_stream.touch()
        db.commit()
    except (TypeError, ValueError) as e:
        db.rollback()
        return web.Response(text="Invalid stream JSON: %r" % e, status=400)
    except ConfigurationError as e:
        db.rollback()
        return web.Response(text="Invalid stream specification: %s" % e, status=400)
    except KeyError as e:
        db.rollback()
        return web.Response(text="Invalid or missing stream attribute: %s" % e, status=400)
    return web.json_response(data=new_stream.to_json())


async def update(request: web.Request):
    db: Session = request.app["db"]
    if request.content_type != 'application/json':
        return web.Response(text='content-type must be application/json', status=400)

    body = await request.json()
    if 'id' not in body:
        return web.Response(text="Invalid request: specify id", status=400)

    my_stream: DataStream = db.get(DataStream, body['id'])
    if my_stream is None:
        return web.Response(text="stream does not exist", status=404)
    if my_stream.locked:
        return web.Response(text="stream is locked", status=400)
    if 'stream' not in body:
        return web.Response(text="Invalid request: specify stream as JSON", status=400)
    try:
        attrs = dict(body['stream'])
    except ValueError:
        return web.Response(text="error: [stream] attribute must be JSON", status=400)
    try:
        my_stream.update_attributes(attrs)
        # make sure name is unique in this destination
        existing_names = [s.name for s in
                          my_stream.folder.data_streams + my_stream.folder.event_streams
                          if s.id != my_stream.id]
        if my_stream.name in existing_names:
            raise ConfigurationError("stream with the same name exists in the folder")
        db.commit()
    except (ValueError, ConfigurationError) as e:
        db.rollback()
        return web.Response(text="Invalid stream specification: %s" % e, status=400)
    return web.json_response(data=my_stream.to_json())


async def delete(request):
    db: Session = request.app["db"]
    data_store: DataStore = request.app["data-store"]
    # find the requested stream
    if 'path' in request.query:
        my_stream = folder.find_stream_by_path(request.query['path'], db, stream_type=DataStream)
    elif 'id' in request.query:
        my_stream = db.get(DataStream, request.query["id"])
    else:
        return web.Response(text="specify an id or a path", status=400)
    if my_stream is None:
        return web.Response(text="stream does not exist", status=404)
    if my_stream.locked or my_stream.active:
        return web.Response(text="locked streams cannot be deleted", status=400)
    await data_store.destroy(my_stream)
    my_stream.folder.touch()
    db.delete(my_stream)
    db.commit()
    return web.Response(text="ok")
