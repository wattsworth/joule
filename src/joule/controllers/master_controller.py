from aiohttp import web
from sqlalchemy.orm import Session, exc
import secrets
from typing import Dict

from joule.api.session import TcpSession
from joule.models.master import Master, make_key
from joule.utilities.misc import detect_url
from joule import errors
from joule import app_keys

# NOTE: This controller is best tested with e2e
# ignored for unittests

async def add(request: web.Request):  # pragma: no cover
    """
    Contact specified node and add self as a follower
    """
    db: Session = request.app[app_keys.db]
    local_name: str = request.app[app_keys.name]
    local_port: int = request.app[app_keys.port]
    local_scheme: str = request.app[app_keys.scheme]
    local_uri: str = request.app[app_keys.base_uri]
    if request.content_type != 'application/json':
        return web.Response(text='content-type must be application/json', status=400)
    body = await request.json()

    try:
        master_type = body['master_type'].lower()
        identifier = body['identifier'].lower()
        if master_type not in ['user', 'joule', 'lumen']:
            return web.Response(text="master_type must be [user|joule|lumen]", status=400)
    except (KeyError, ValueError) as e:
        return web.Response(text="Invalid request %s" % str(e), status=400)
    my_master = None
    try:
        if master_type == 'user':
            # check if this name is associated with a master entry
            my_master = db.query(Master). \
                filter(Master.type == Master.TYPE.USER). \
                filter(Master.name == identifier).first()
            if my_master is not None:
                return web.Response(text="User already exists", status=400)
            # see if API key was included in request
            if 'api_key' in body and body['api_key'] is not None:
                key = body['api_key']
                if len(key) < 32:
                    return web.Response(text="API Key must be at least 32 characters", status=400)
            else:
                key = make_key()  # make a new key
            # create a new user API key
            my_master = Master(name=identifier,
                               type=Master.TYPE.USER,
                               key=key)
            grantor_key = request.headers["X-API-KEY"]
            my_master.grantor_id = db.query(Master.id).filter(
                Master.key == grantor_key).one()[0]
            db.add(my_master)
            db.commit()
            return web.json_response({"key": my_master.key,
                                      "name": local_name})
        elif master_type == 'joule' or master_type == 'lumen':
            # create a new node API key
            my_master = Master()
            my_master.key = make_key()
            if master_type == 'joule':
                my_master.type = Master.TYPE.JOULE_NODE
            else:
                my_master.type = Master.TYPE.LUMEN_NODE
            grantor_key = request.headers["X-API-KEY"]

            my_master.grantor_id = db.query(Master.id).filter(
                Master.key == grantor_key).one()[0]
            # make a temporary name
            my_master.name = "pending_%s" % secrets.token_hex(5)
            db.add(my_master)
            db.commit()
            # post this key to the master
            # keep track of whether the operation is successful, don't fail on error
            # because it might not be possible to coordinate the correct URL's, let the user
            # fix this later through the Lumen web interface or some other way.
            success = False
            error_msg = ""
            if master_type == 'joule':
                coro = _send_node_key(my_master.key, identifier, local_port,
                                      local_name, local_scheme, local_uri, request.app[app_keys.cafile])
            else:
                coro = _send_lumen_key(my_master.key, identifier, local_port,
                                       local_name, local_scheme, local_uri, request.app[app_keys.cafile],
                                       body['lumen_params'])
            try:
                name = await coro
                success = True
            except errors.ApiError as e:
                error_msg = str(e)
                name = identifier
                success = False

            # remove the key for this node if it already exists
            db.query(Master). \
                filter(Master.type == my_master.type). \
                filter(Master.name == name).delete()
            my_master.name = name
            db.add(my_master)
            db.commit()
            if success:
                return web.json_response({"name": my_master.name})
            else:
                return web.json_response({"lumen error": error_msg}, status=400)
    except (ValueError, KeyError) as e:
        if my_master is not None:
            db.delete(my_master)
            db.commit()
        return web.Response(text="Cannot add master: [%s]" % str(e), status=400)


async def _send_node_key(key: str,
                         identifier: str,
                         local_port: int,
                         local_name: str,
                         local_scheme: str,
                         local_uri: str,
                         cafile: str) -> str:  # pragma: no cover
    # if the identifier is an IP address or a domain name, turn it into a URL
    if not identifier.startswith("http"):
        url = await detect_url(identifier, 443)
        if url is None:
            raise errors.ApiError("cannot connect to [%s] on port 443" % identifier)
    else:
        url = identifier

    session = TcpSession(url, key, cafile)
    params = {'key': key,
              'port': local_port,
              'name': local_name,
              'base_uri': local_uri,
              'scheme': local_scheme}
    if cafile != "":
        params["name_is_host"] = 1
    resp = await session.post("/follower.json", json=params)
    await session.close()
    return resp['name']


async def _send_lumen_key(key: str,
                          identifier: str,
                          local_port: int,
                          local_name: str,
                          local_scheme: str,
                          local_uri: str,
                          cafile: str,
                          lumen_params: Dict) -> str:  # pragma: no cover
    # if the identifier is an IP address or a domain name, turn it into a URL
    if not identifier.startswith("http"):
        url = await detect_url(identifier + "/lumen")
        if url is None:
            raise errors.ApiError("cannot connect to [%s] on port 80 or 443" % identifier)
    else:
        url = identifier

    # no key needed to access the lumen /nilms end point
    session = TcpSession(url, "stub_key", cafile)
    params = {'api_key': key,
              'port': local_port,
              'name': local_name,
              'base_uri': local_uri,
              'scheme': local_scheme}
    if lumen_params is not None:
        params = {**params, **lumen_params}
    # TODO enable this for CA checking on Lumen server
    # if cafile != "":
    #    params["name_is_host"] = 1
    try:
        await session.post("/nilms.json", json=params)
    except errors.ApiError as e:
        raise e
    finally:
        await session.close()
    return identifier


async def index(request: web.Request):
    db: Session = request.app[app_keys.db]
    masters = db.query(Master).all()
    return web.json_response([m.to_json() for m in masters])


async def delete(request: web.Request):
    """
    Remove the specified node from the list of masters
    """
    db: Session = request.app[app_keys.db]
    node_name: str = request.app[app_keys.name]
    # to eliminate uninitialized warnings
    str_master_type = ""
    name = ""
    try:
        name = request.query["name"]
        str_master_type = request.query["master_type"]
        if str_master_type != "user":
            str_master_type += "_node"
        master_type = Master.TYPE[str_master_type.upper()]
        master = db.query(Master). \
            filter(Master.name == name). \
            filter(Master.type == master_type). \
            one()
        if master.key == request.headers["X-API-KEY"]:
            return web.Response(text="cannot delete yourself, this would lock you out of the node", status=400)

        db.delete(master)
    except (KeyError, ValueError):
        return web.Response(text="specify name and master_type", status=400)
    except exc.NoResultFound:
        return web.Response(text="%s [%s] is not a master of node [%s]" % (str_master_type, name, node_name),
                            status=404)
    db.commit()
    return web.Response(text="ok")
