from aiohttp import web
from sqlalchemy.orm import Session
from joule.models import Stream, Folder, DataStore
from typing import List, Optional
import pdb

from joule.models import folder


async def index(request: web.Request):
    db: Session = request.app["db"]
    root = folder.root(db)
    return web.json_response(root.to_json())


async def info(request: web.Request):
    db: Session = request.app["db"]
    data_store: DataStore = request.app["data-store"]

    root = folder.root(db)
    if 'path' in request.query:
        stream = _find_stream_by_path(
            request.query['path'][1:].split('/'), root)
    elif 'id' in request.query:
        stream = db.query(Stream).get(request.query["id"])
    else:
        return web.Response(text="specify an id or a path", status=400)
    if stream is None:
        return web.Response(text="stream does not exist", status=404)
    stream_info = await data_store.info(stream)
    return web.json_response({"stream": stream.to_json(),
                              "data-info": stream_info.to_json()})


async def update(request):
    return web.Response(text="TODO",
                        content_type='application/json')


async def delete(request):
    return web.Response(text="TODO",
                        content_type='application/json')


def _find_stream_by_path(path: List[str], parent: Folder) -> Optional[Stream]:
    if len(path) == 1:
        for stream in parent.streams:
            if stream.name == path[0]:
                return stream
        else:
            return None
    for child in parent.children:
        if child.name == path[0]:
            return _find_stream_by_path(path[1:], child)
    else:
        return None
