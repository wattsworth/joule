from aiohttp import web
from sqlalchemy.orm import Session
import json

from joule.models import folder, Folder, Stream, Element


async def index(request: web.Request):
    db: Session = request.app["db"]
    root = folder.root(request.app['db'])

    if request.query["normalize"]:
        data = json.dumps({
            "root_id": root.id,
            "folders": db.query(Folder).all(),
            "streams": db.query(Stream).all(),
            "elements": db.query(Element).all()
        })
    else:
        data = json.dumps(root.to_json())

    return web.Response(text=data,
                        content_type='text/json')


async def update(request):
    return web.Response(text="TODO",
                        content_type='/text/json')


async def delete(request):
    return web.Response(text="TODO",
                        content_type='/text/json')
