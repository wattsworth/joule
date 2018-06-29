from aiohttp import web
from sqlalchemy.orm import Session
from joule.models import Stream, Folder, DataStore, stream
import json
from typing import List, Optional
import pdb

from joule.models import folder, ConfigurationError


async def index(request: web.Request):
    db: Session = request.app["db"]
    root = folder.root(db)
    return web.json_response(root.to_json())


async def info(request: web.Request):
    db: Session = request.app["db"]
    data_store: DataStore = request.app["data-store"]
    if 'path' in request.query:
        stream = folder.find_stream_by_path(request.query['path'], db)
    elif 'id' in request.query:
        stream = db.query(Stream).get(request.query["id"])
    else:
        return web.Response(text="specify an id or a path", status=400)
    if stream is None:
        return web.Response(text="stream does not exist", status=404)
    stream_info = await data_store.info(stream)
    return web.json_response({"stream": stream.to_json(),
                              "data-info": stream_info.to_json()})


async def move(request: web.Request):
    db: Session = request.app["db"]
    body = await request.post()
    # find the stream
    if 'path' in body:
        stream = folder.find_stream_by_path(body['path'], db)
    elif 'id' in body:
        stream = db.query(Stream).get(body["id"])
    else:
        return web.Response(text="specify an id or a path", status=400)
    if stream is None:
        return web.Response(text="stream does not exist", status=404)
    # find or create the destination folder
    if 'destination' not in body:
        return web.Response(text="specify a destination", status=400)
    try:
        destination = folder.find_or_create(body['destination'], db)
    except ConfigurationError as e:
        return web.Response(text=e, status=400)
    # make sure there are no other streams with the same name here
    for peer in destination.streams:
        if peer.name == stream.name:
            return web.Response(text="a stream with this name is in the destination folder",
                                status=400)
    destination.streams.append(stream)
    db.commit()
    return web.json_response({"stream": stream.to_json()})


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
        return web.Response(text=e, status=400)
    return web.json_response(data=new_stream.to_json())


async def update(request):
    return web.Response(text="TODO",
                        content_type='application/json')


async def delete(request):
    return web.Response(text="TODO",
                        content_type='application/json')

