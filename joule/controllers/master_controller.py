from aiohttp import web
from sqlalchemy.orm import Session, exc
import secrets
import aiohttp
import ssl

from joule.api.session import TcpSession
from joule.models.master import Master, make_key


async def add(request: web.Request):
    """
    Contact specified node and add self as a follower
    """
    db: Session = request.app["db"]
    node_name: str = request.app["name"]
    port: int = request.app["port"]
    cafile = request.app["cafile"]
    if request.content_type != 'application/json':
        return web.Response(text='content-type must be application/json', status=400)
    body = await request.json()

    try:
        master_type = body['master_type'].lower()
        identifier = body['identifier'].lower()
        if master_type not in ['user', 'node']:
            raise ValueError("master_type must be [user|node]")
    except (KeyError, ValueError) as e:
        return web.Response(text="Invalid request %s" % str(e))
    my_master = None
    try:
        if master_type == 'user':
            # check if this name is associated with a master entry
            my_master = db.query(Master). \
                filter(Master.type == Master.TYPE.USER). \
                filter(Master.name == identifier).first()
            if my_master is None:
                # create a new user API key
                my_master = Master(name=identifier,
                                   type=Master.TYPE.USER,
                                   key=make_key())
                grantor_key = request.headers["X-API-KEY"]
                my_master.grantor_id = db.query(Master.id).filter(
                    Master.key == grantor_key).one()
                db.add(my_master)
                db.commit()
            return web.json_response({"key": my_master.key,
                                      "name": node_name})
        elif master_type == 'node':
            # create a new node API key
            my_master = Master()
            my_master.key = make_key()
            my_master.type = Master.TYPE.NODE
            grantor_key = request.headers["X-API-KEY"]
            my_master.grantor_id = db.query(Master.id).filter(
                Master.key == grantor_key).one()
            # make a temporary name
            my_master.name = "pending_%s" % secrets.token_hex(5)
            db.add(my_master)
            db.commit()
            # post this key to the master
            name = await _send_key(my_master.key, identifier, port,
                                   node_name, request.app["cafile"], request.app["name"])

            # remove the key for this node if it already exists
            db.query(Master). \
                filter(Master.type == Master.TYPE.NODE). \
                filter(Master.name == name).delete()
            my_master.name = name
            db.add(my_master)
            db.commit()
            return web.json_response({"name": my_master.name})
    except (ValueError, KeyError) as e:
        if my_master is not None:
            db.delete(my_master)
            db.commit()
        return web.Response(text="Cannot add master: [%s]" % str(e), status=400)


async def _send_key(key: str,
                    identifier: str,
                    local_port: int,
                    local_name: str,
                    cafile: str,
                    host: str) -> str:
    # TODO handle CA, http(s) identification, lumen auth, etc
    if not identifier.startswith("http"):
        url = "https://" + identifier + ":8088"
    else:
        url = identifier
    print("connecting to node at [%s] =====" % url)
    session = TcpSession(url, key, cafile)
    params = {'key': key,
              'port': local_port,
              'name': local_name}
    if cafile != "":
        params["host"] = host
    resp = await session.post("/follower.json", json=params)
    await session.close()
    return resp['name']


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
        master = db.query(Master). \
            filter(Master.name == name). \
            filter(Master.type == master_type). \
            one()
        if master.key == request.headers["X-API-KEY"]:
            return web.Response(text="cannot delete yourself, this would lock you out of the node", status=400)

        db.delete(master)
    except ValueError:
        return web.Response(text="specify name and master_type", status=400)
    except exc.NoResultFound:
        return web.Response(text="%s [%s] is not a master of node [%s]" % (str_master_type, name, node_name),
                            status=404)
    db.commit()
    return web.Response(text="ok")
