import datetime

from aiohttp import web
from sqlalchemy.orm import Session
from joule.models import (
    DataStream,
    DataStore,
    data_stream)

from joule.models import folder, Folder
from joule.controllers.helpers import read_json, get_stream_from_request_params
from joule.errors import ConfigurationError
from joule import app_keys

async def info(request: web.Request):
    db: Session = request.app[app_keys.db]
    data_store: DataStore = request.app[app_keys.data_store]
    my_stream = get_stream_from_request_params(request, db)
    if "no-info" in request.query:
        stream_info = None
    else:
        stream_info = await data_store.info([my_stream])
    return web.json_response(my_stream.to_json(stream_info))


async def move(request: web.Request):
    db: Session = request.app[app_keys.db]
    body = await read_json(request)
    # find the stream
    if 'src_path' in body:
        my_stream = folder.find_stream_by_path(body['src_path'], db, stream_type=DataStream)
    elif 'src_id' in body:
        my_stream = db.get(DataStream, body["src_id"])
    else:
        raise web.HTTPBadRequest(reason="specify a source id or a path")
    if my_stream is None:
        raise web.HTTPNotFound(reason="stream does not exist")
    if my_stream.locked:
        raise web.HTTPBadRequest(reason="locked streams cannot be moved")
    # find or create the destination folder
    if 'dest_path' in body:
        try:
            destination = folder.find(body['dest_path'], db, create=True)
        except ConfigurationError as e:
            raise web.HTTPBadRequest(reason="Destination error: %s" % str(e))
    elif 'dest_id' in body:
        destination = db.get(Folder, body["dest_id"])
    else:
        raise web.HTTPBadRequest(reason="specify a destination")
    # make sure name is unique in this destination
    existing_names = [s.name for s in destination.data_streams + destination.event_streams]
    if my_stream.name in existing_names:
        db.rollback()
        raise web.HTTPBadRequest(reason="stream with the same name exists in the destination folder")
    my_stream.touch()
    destination.data_streams.append(my_stream)
    destination.touch()
    db.commit()
    return web.json_response({"stream": my_stream.to_json()})


async def create(request):
    db: Session = request.app[app_keys.db]
    body = await read_json(request)

    if 'stream' not in body:
        raise web.HTTPBadRequest(reason="provide a stream")

    # find or create the destination folder
    if 'dest_path' in body:
        try:
            destination = folder.find(body['dest_path'], db, create=True)
        except ConfigurationError as e:
            raise web.HTTPBadRequest(reason="Destination error: %s" % str(e))
    elif 'dest_id' in body:
        destination = db.get(Folder, body["dest_id"])
    else:
        raise web.HTTPBadRequest(reason="specify a destination")

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
        raise web.HTTPBadRequest(reason="Invalid stream JSON: %r" % e)
    except ConfigurationError as e:
        db.rollback()
        raise web.HTTPBadRequest(reason="Invalid stream specification: %s" % e)
    except KeyError as e:
        db.rollback()
        raise web.HTTPBadRequest(reason="Invalid or missing stream attribute: %s" % e)
    return web.json_response(data=new_stream.to_json())


async def update(request: web.Request):
    db: Session = request.app[app_keys.db]
    body = await read_json(request)
    if 'id' not in body:
        raise web.HTTPBadRequest(reason="Invalid request: specify id")

    my_stream: DataStream = db.get(DataStream, body['id'])
    if my_stream is None:
        raise web.HTTPNotFound(reason="stream does not exist")
    if my_stream.locked:
        raise web.HTTPBadRequest(reason="stream is locked")
    if 'stream' not in body:
        raise web.HTTPBadRequest(reason="Invalid request: specify stream as JSON")
    try:
        attrs = dict(body['stream'])
    except ValueError:
        raise web.HTTPBadRequest(reason="error: [stream] attribute must be JSON")
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
        raise web.HTTPBadRequest(reason="Invalid stream specification: %s" % e)
    return web.json_response(data=my_stream.to_json())


async def delete(request):
    db: Session = request.app[app_keys.db]
    data_store: DataStore = request.app[app_keys.data_store]
    # find the requested stream
    my_stream = get_stream_from_request_params(request, db)
    if my_stream.locked or my_stream.active:
        raise web.HTTPBadRequest(reason="locked streams cannot be deleted")
    await data_store.destroy(my_stream)
    my_stream.folder.touch()
    db.delete(my_stream)
    db.commit()
    return web.Response(text="ok")
