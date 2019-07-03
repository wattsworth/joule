from aiohttp import web
import json
from sqlalchemy.exc import CircularDependencyError
from sqlalchemy.orm import Session
from typing import List

from joule.models import folder, Folder, DataStore
from joule.errors import ConfigurationError


async def info(request: web.Request):
    db: Session = request.app["db"]
    if 'path' in request.query:
        my_folder = folder.find(request.query['path'], db)
    elif 'id' in request.query:
        my_folder = db.query(Folder).get(request.query["id"])
    else:
        return web.Response(text="specify an id or path", status=400)
    if my_folder is None:
        return web.Response(text="folder does not exist", status=404)
    return web.json_response(my_folder.to_json())


async def move(request):
    db: Session = request.app["db"]
    if request.content_type != 'application/json':
        return web.Response(text='content-type must be application/json', status=400)
    body = await request.json()
    # find the folder
    if 'src_path' in body:
        my_folder = folder.find(body['src_path'], db)
    elif 'src_id' in body:
        my_folder = db.query(folder.Folder).get(body["src_id"])
    else:
        return web.Response(text="specify an id or a path", status=400)
    if my_folder is None:
        return web.Response(text="folder does not exist", status=404)
    # make sure the folder is not locked
    if my_folder.locked:
        return web.Response(text="folder is locked", status=400)
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
    # make sure name is unique in the folder
    peer_names = [f.name for f in destination.children]
    if my_folder.name in peer_names:
        db.rollback()
        return web.Response(text="a folder with this name is in the destination folder",
                            status=400)
    try:
        # make sure this does not create a circular graph
        parent = destination.parent
        while parent is not None:
            if parent == my_folder:
                raise ValueError()
            parent = parent.parent
        destination.children.append(my_folder)
        db.commit()
    except (CircularDependencyError, ValueError):
        db.rollback()
        return web.Response(text="cannot place a parent in a child folder",
                            status=400)
    return web.json_response({"stream": my_folder.to_json()})


async def update(request):
    db: Session = request.app["db"]
    if request.content_type != 'application/json':
        return web.Response(text='content-type must be application/json', status=400)
    body = await request.json()
    if 'id' not in body:
        return web.Response(text="Invalid request: specify id", status=400)

    my_folder: Folder = db.query(Folder).get(body['id'])
    if my_folder is None:
        return web.Response(text="folder does not exist", status=404)
    if my_folder.locked:
        return web.Response(text="folder is locked", status=400)
    if 'folder' not in body:
        return web.Response(text="Invalid request: specify folder as JSON", status=400)
    try:
        attrs = dict(body['folder'])
    except ValueError:
        return web.Response(text="error: [folder] attribute must be JSON", status=400)
    try:
        my_folder.update_attributes(attrs)
        # make sure name is unique in the folder
        peer_names = [f.name for f in my_folder.parent.children if f.id != my_folder.id]
        if my_folder.name in peer_names:
            db.rollback()
            return web.Response(text="a folder with this name is in the destination folder",
                                status=400)
        db.commit()
    except (ValueError, ConfigurationError) as e:
        db.rollback()
        return web.Response(text="error: %s" % e, status=400)
    return web.json_response(data=my_folder.to_json())


async def delete(request):
    db: Session = request.app["db"]
    data_store: DataStore = request.app["data-store"]

    # find the requested folder
    if 'path' in request.query:
        my_folder: Folder = folder.find(request.query['path'], db)
    elif 'id' in request.query:
        my_folder = db.query(Folder).get(request.query["id"])
    else:
        return web.Response(text="specify an id or a path", status=400)
    if my_folder is None:
        return web.Response(text="folder does not exist", status=404)
    if my_folder.locked:
        return web.Response(text="folder is locked", status=400)
    if 'recursive' in request.query and request.query["recursive"] == '1':
        await _recursive_delete(my_folder.children, db, data_store)
    elif len(my_folder.children) > 0:
        return web.Response(text="specify [recursive] or remove child folders first", status=400)

    for stream in my_folder.streams:
        if stream.locked:  # pragma: no cover
            # shouldn't ever get here because of the check above, but just in case
            return web.Response(text="cannot delete folder with locked streams", status=400)
        await data_store.destroy(stream)
        db.delete(stream)

    db.delete(my_folder)
    db.commit()
    return web.Response(text="ok")


async def _recursive_delete(folders: List[Folder], db: Session, data_store: DataStore):
    if len(folders) == 0:
        return
    for f in folders:
        for stream in f.streams:
            if stream.locked:  # pragma: no cover
                # shouldn't ever get here because a locked folder shouldn't call us
                raise ConfigurationError("cannot delete folder with locked streams")
            await data_store.destroy(stream)
            db.delete(stream)
        await _recursive_delete(f.children, db, data_store)
        db.delete(f)
