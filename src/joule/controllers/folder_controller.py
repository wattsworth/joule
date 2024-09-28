from aiohttp import web
from sqlalchemy.exc import CircularDependencyError
from sqlalchemy.orm import Session
from typing import List

from joule.constants import ApiErrorMessages
from joule.models import folder, Folder, EventStore, DataStore, DataStream, EventStream
from joule.errors import ConfigurationError
from joule import app_keys

async def index(request: web.Request):
    db: Session = request.app[app_keys.db]
    data_store: DataStore = request.app[app_keys.data_store]
    event_store: DataStore = request.app[app_keys.event_store]

    root = folder.root(db)
    if 'data-info' in request.query:
        data_streams = db.query(DataStream).all()
        data_streams_info = await data_store.info(data_streams)
        event_streams = db.query(EventStream).all()
        event_streams_info = await event_store.info(event_streams)
    else:
        data_streams_info = {}
        event_streams_info = {}
    resp = root.to_json(data_streams_info, event_streams_info)
    # get a list of the ids of all DataStreams that are either a source or a destination
    query_result = db.query(DataStream). \
        filter((DataStream.is_source == True) | (DataStream.is_destination == True)) \
        .with_entities(DataStream.id).all()
    resp['active_data_streams'] = [r[0] for r in query_result]
    return web.json_response(resp)


async def info(request: web.Request):
    db: Session = request.app[app_keys.db]
    if 'path' in request.query:
        my_folder = folder.find(request.query['path'], db)
    elif 'id' in request.query:
        my_folder = db.get(Folder, request.query["id"])
    else:
        raise web.HTTPBadRequest(reason=ApiErrorMessages.specify_id_or_path)
    if my_folder is None:
        raise web.HTTPNotFound(reason=ApiErrorMessages.folder_does_not_exist)
    return web.json_response(my_folder.to_json())


async def move(request):
    db: Session = request.app[app_keys.db]
    if request.content_type != 'application/json':
        raise web.HTTPBadRequest(reason='content-type must be application/json')
    body = await request.json()
    # find the folder
    if 'src_path' in body:
        my_folder = folder.find(body['src_path'], db)
    elif 'src_id' in body:
        my_folder = db.get(folder.Folder, body["src_id"])
    else:
        raise web.HTTPBadRequest(reason=ApiErrorMessages.specify_id_or_path)
    if my_folder is None:
        raise web.HTTPNotFound(reason=ApiErrorMessages.folder_does_not_exist)
    # make sure the folder is not locked
    if my_folder.locked:
        raise web.HTTPBadRequest(reason=ApiErrorMessages.folder_is_locked)
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
    
    # make sure name is unique in the folder
    peer_names = [f.name for f in destination.children]
    if my_folder.name in peer_names:
        db.rollback()
        raise web.HTTPBadRequest(reason="a folder with this name is in the destination folder")
    try:
        # make sure this does not create a circular graph
        parent = destination.parent
        while parent is not None:
            if parent == my_folder:
                raise ValueError()
            parent = parent.parent
        my_folder.touch()
        destination.touch()
        destination.children.append(my_folder)
        db.commit()
    except (CircularDependencyError, ValueError):
        db.rollback()
        raise web.HTTPBadRequest(reason="cannot place a parent in a child folder")
    return web.json_response({"stream": my_folder.to_json()})


async def update(request):
    db: Session = request.app[app_keys.db]
    if request.content_type != 'application/json':
        raise web.HTTPBadRequest(reason='content-type must be application/json')
    body = await request.json()
    if 'id' not in body:
        raise web.HTTPBadRequest(reason="Invalid request: specify id")

    my_folder: Folder = db.get(Folder, body['id'])
    if my_folder is None:
        raise web.HTTPNotFound(reason=ApiErrorMessages.folder_does_not_exist)
    if my_folder.locked:
        raise web.HTTPBadRequest(reason=ApiErrorMessages.folder_is_locked)
    if 'folder' not in body:
        raise web.HTTPBadRequest(reason="Invalid request: specify folder as JSON")
    try:
        attrs = dict(body['folder'])
    except ValueError:
        raise web.HTTPBadRequest(reason="error: [folder] attribute must be JSON")
    try:
        my_folder.update_attributes(attrs)
        # make sure name is unique in the folder
        peer_names = [f.name for f in my_folder.parent.children if f.id != my_folder.id]
        if my_folder.name in peer_names:
            db.rollback()
            return web.Response(text="a folder with this name is in the destination folder",
                                status=400)
        my_folder.touch()
        db.commit()
    except (ValueError, ConfigurationError) as e:
        db.rollback()
        raise web.HTTPBadRequest(reason="error: %s" % e)
    return web.json_response(data=my_folder.to_json())


async def delete(request):
    db: Session = request.app[app_keys.db]
    data_store: DataStore = request.app[app_keys.data_store]
    event_store: EventStore = request.app[app_keys.event_store]
    # find the requested folder
    if 'path' in request.query:
        my_folder: Folder = folder.find(request.query['path'], db)
    elif 'id' in request.query:
        my_folder = db.get(Folder, request.query["id"])
    else:
        raise web.HTTPBadRequest(reason="specify an id or a path")
    if my_folder is None:
        raise web.HTTPNotFound(reason=ApiErrorMessages.folder_does_not_exist)
    if my_folder.locked:
        raise web.HTTPBadRequest(reason=ApiErrorMessages.folder_is_locked)
    if 'recursive' in request.query and request.query["recursive"] == '1':
        await _recursive_delete(my_folder.children, db, data_store, event_store)
    elif len(my_folder.children) > 0:
        raise web.HTTPBadRequest(reason="specify [recursive] or remove child folders first")

    for stream in my_folder.data_streams:
        if stream.locked:  # pragma: no cover
            # shouldn't ever get here because of the check above, but just in case
            raise web.HTTPBadRequest(reason="cannot delete folder with locked streams")
        await data_store.destroy(stream)
        db.delete(stream)
    for stream in my_folder.event_streams:
        await event_store.destroy(stream)
        db.delete(stream)

    db.delete(my_folder)
    # update the parent timestamps
    my_folder.parent.touch()
    db.commit()
    return web.Response(text="ok")


async def _recursive_delete(folders: List[Folder], db: Session, data_store: DataStore,
                            event_store: EventStore):
    if len(folders) == 0:
        return
    for f in folders:
        for stream in f.data_streams:
            if stream.locked:  # pragma: no cover
                # shouldn't ever get here because a locked folder shouldn't call us
                raise web.HTTPBadRequest(reason="cannot delete folder with locked streams")
            await data_store.destroy(stream)
            db.delete(stream)
        for stream in f.event_streams:
            await event_store.destroy(stream)
            db.delete(stream)
        await _recursive_delete(f.children, db, data_store, event_store)
        db.delete(f)
