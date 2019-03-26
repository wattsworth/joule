from aiohttp import web
from sqlalchemy.orm import Session
import sqlalchemy

from joule.models.master import Master, make_key


async def index(request: web.Request):
    db: Session = request.app["db"]
    masters = db.query(Master)
    return web.json_response([m.to_json for m in masters])


async def add(request: web.Request):
    """
    Contact specified node and add self as a follower
    """
    db: Session = request.app["db"]

    try:
        master_type = request.query['type'].lower()
        if master_type == 'user':
            # create a new user API key
            my_master = Master()
            my_master.name = request.query["name"]
            my_master.key = make_key()
            my_master.type = Master.TYPE.USER
            grantor_key = request.headers["JOULE_API_KEY"]
            my_master.grantor_id = db.query(Master.id).get(
                Master.key == grantor_key)
            return web.Response(text=my_master.key)
        else:
            return web.Response(text="TODO", status=500)
    except KeyError as e:
        return web.Response(text="Missing [%s] parameter" % str(e), status=400)
    except ValueError as e:
        return web.Response(text="Invalid value for parameter: [%s]" % str(e), status=400)


async def delete(request: web.Request):
    """
    Remove the specified node from the list of masters
    """
    db: Session = request.app["db"]
    if "id" not in request.query:
        return web.Response(text="specity id to remove", status=400)
    node_id = request.query["id"]
    if not db.query(Master).filter(Master.id==id).exists():
        return web.Response(text="invalid id", status=400)

    master = db.query(Master).get(node_id)
    db.delete(master)
    db.commit()
    return web.Response(text="OK")
