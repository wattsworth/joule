from aiohttp import web
from sqlalchemy.orm import Session

from joule.models import master


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
        type = request.query['type'].lower()
        if type=='user':
            # create a new user API key
            my_master = master.Master()
            my_master.name = request.query["name"]
            my_master.key = master.make_key()
            my_master.type = master.Master.TYPE.USER
            grantor_key = request.headers["JOULE_API_KEY"]
            my_master.grantor_id = db.query(master.Master.id).filter(
                key==grantor_key).first
            return web.Response(text=my_master.key)
        else:
            async with aiohttp.client.post(session_key)
                # send my name, the key, and the port
            request.host
            # contact the node with an API key
    except KeyError as e:
        return web.Response(text="Missing [%s] parameter" % str(e))
    except ValueError as e:
        return web.Response(text="Invalid value for parameter: [%s]" % str(e))


async def delete(request: web.Request):
    """
    Remove the specified node from the list of masters
    """
    if name in request.query:
        name = request.query["name"]
        master = self.db.query(Master).filter(name==name)
    elif "id" in request.query:
        node_id = request.query["id"]
        master = self.db.query(Master).filter(id==node_id)
    else:
        return web.Response(text="specify name or id to remove", status=400)
    db.delete(master)
    db.commit()
    return web.Response(text="OK")

