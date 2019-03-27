from aiohttp import web
from sqlalchemy.orm import Session, exc

from joule.models.master import Master, make_key


async def add(request: web.Request):
    """
    Contact specified node and add self as a follower
    """
    db: Session = request.app["db"]
    try:
        master_type = request.query['master_type'].lower()
        identifier = request.query['identifier'].lower()
        if master_type not in ['user', 'node']:
            raise ValueError("master_type must be [user|node]")
    except (KeyError, ValueError) as e:
        return web.Response(text="Invalid request %s" % str(e))
    try:
        if master_type == 'user':
            # create a new user API key
            my_master = Master()
            my_master.name = identifier
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


async def index(request: web.Request):
    db: Session = request.app["db"]
    masters = db.query(Master).all()
    return web.json_response([m.to_json() for m in masters])


async def delete(request: web.Request):
    """
    Remove the specified node from the list of masters
    """
    db: Session = request.app["db"]
    node_name: str = request.app["name"]
    try:
        name = request.query["name"]
        str_master_type = request.query["master_type"]
        master_type = Master.TYPE[str_master_type.upper()]
        master = db.query(Master).\
            filter(Master.name == name).\
            filter(Master.type == master_type).\
            one()
        db.delete(master)
    except ValueError:
        return web.Response(text="specify name and master_type", status=400)
    except exc.NoResultFound:
        return web.Response(text="%s [%s] is not a master of node [%s]" % (str_master_type, name, node_name), status=404)
    db.commit()
    return web.Response(text="OK")
