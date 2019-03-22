from aiohttp import web
from sqlalchemy.orm import Session

from joule.models import Master


async def index(request: web.Request):
    db: Session = request.app["db"]
    masters = db.query(Master)
    return web.json_response([m.to_json for m in masters])

