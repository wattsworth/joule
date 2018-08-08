from aiohttp import web
import json
from sqlalchemy.orm import Session
from typing import List

from joule.models import folder, Folder, ConfigurationError


async def move(request):
    db: Session = request.app["db"]
    body = await request.post()
    # find the folder
    if 'path' in body:
        my_folder = folder.find(body['path'], db)
    elif 'id' in body:
        my_folder = db.query(folder.Folder).get(body["id"])
    else:
        return web.Response(text="specify an id or a path", status=400)
    if my_folder is None:
        return web.Response(text="folder does not exist", status=404)
    if my_folder.locked:
        return web.Response(text="folder is locked", status=400)
    # find or create the destination folder
    if 'destination' not in body:
        return web.Response(text="specify a destination", status=400)
    try:
        destination = folder.find(body['destination'], db, create=True)
    except ConfigurationError as e:
        return web.Response(text="Destination error: %s" % str(e), status=400)
    # make sure there are no other streams with the same name here
    for peer in destination.folders:
        if peer.name == my_folder.name:
            return web.Response(text="a folder with this name is in the destination folder",
                                status=400)
    destination.folders.append(my_folder)
    db.commit()
    return web.json_response({"stream": my_folder.to_json()})


async def update(request):
    db: Session = request.app["db"]
    body = await request.post()
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
        attrs = json.loads(body['folder'])
    except ValueError:
        return web.Response(text="error: [folder] attribute must be JSON", status=400)
    try:
        my_folder.update_attributes(attrs)
        db.commit()
    except (ValueError, ConfigurationError) as e:
        db.rollback()
        return web.Response(text="error: %s" % e, status=400)
    return web.json_response(data=my_folder.to_json())


async def delete(request):
    db: Session = request.app["db"]
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
        return web.Response(text="locked folders cannot be deleted", status=400)
    if 'recursive' in request.query:
        recursive = True
    else:
        recursive = False
    # check to see this folder can be deleted
    if not my_folder.contains_streams:
        return web.Response(text="remove all streams before deleting the folder", status=400)
    if recursive:
        _recursive_delete(my_folder.children, db)
    if not recursive and len(my_folder.children) > 0:
        return web.Response(text="specify [recursive] or remove child folders first", status=400)

    db.delete(my_folder)
    db.commit()
    return web.Response(text="ok")


def _recursive_delete(folders: List[Folder], db: Session):
    if len(folders) == 0:
        return
    for f in folders:
        _recursive_delete(f.children, db)
        db.delete(f)
