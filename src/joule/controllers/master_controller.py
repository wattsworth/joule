from aiohttp import web
from sqlalchemy.orm import Session, exc
import secrets
from typing import Dict

from joule.api.session import TcpSession
from joule.models.master import Master, make_key
from joule.utilities.misc import detect_url
from joule import errors
from joule import app_keys
from joule.controllers.helpers import read_json
from joule.constants import EndPoints

async def index(request: web.Request):
    db: Session = request.app[app_keys.db]
    masters = db.query(Master).all()
    return web.json_response([m.to_json() for m in masters])

async def add(request: web.Request):
    """
    Contact specified node and add self as a follower
    """
    db: Session = request.app[app_keys.db]
    local_name: str = request.app[app_keys.name]
    body = await read_json(request)
    try:
        master_type = body['master_type'].lower()
        if master_type not in ['user', 'joule', 'lumen']:
            raise web.HTTPBadRequest(reason="master_type must be [user|joule|lumen]")
        
        # Use the API token that authenticated this request to find the master who
        # is granting access to this user/node
        grantor_key = request.headers["X-API-KEY"]
        grantor_id = db.query(Master.id).filter(Master.key == grantor_key).one()[0]

        # How we add the master depends on the type, a user or a node (joule or lumen)
        if master_type == 'user':
            return _add_user(db, body, local_name, grantor_id)
        elif master_type == 'joule' or master_type == 'lumen':
            local_port: int = request.app[app_keys.port]
            local_scheme: str = request.app[app_keys.scheme]
            local_uri: str = request.app[app_keys.base_uri]
            cafile = request.app[app_keys.cafile]
            return await _add_device(db, master_type, body, local_name, local_port, local_scheme, local_uri, cafile, grantor_id)
        
    except (KeyError, ValueError) as e:
            raise web.HTTPBadRequest(reason="Invalid request %s" % str(e))
        
### BEGIN: Helper Functions for Add ###

def _add_user(db: Session, data: Dict, local_name: str, grantor_id) -> web.Response:
    # check if this name is associated with a master entry
    my_master = db.query(Master). \
        filter(Master.type == Master.TYPE.USER). \
        filter(Master.name == data['identifier']).first()
    if my_master is not None:
        raise web.HTTPBadRequest(reason="User already exists")
    # see if API key was included in request
    if 'api_key' in data and data['api_key'] is not None:
        key = data['api_key']
        if len(key) < 32:
            raise web.HTTPBadRequest(reason="API Key must be at least 32 characters")
    # otherwise make a new key
    else:
        key = make_key()
    my_master = Master(name=data['identifier'],
                        type=Master.TYPE.USER,
                        grantor_id=grantor_id,
                        key=key)
    db.add(my_master)
    db.commit()
    return web.json_response({"key": my_master.key,
                              "name": local_name})
    
    

async def _add_device(db: Session, master_type: str, data: Dict, local_name: str, port, scheme, uri, cafile, grantor_id) -> web.Response:
    try:
        # create a new node API key
        my_master = Master(key=make_key(), grantor_id=grantor_id)
        if master_type == 'joule':
            my_master.type = Master.TYPE.JOULE_NODE
        else:
            my_master.type = Master.TYPE.LUMEN_NODE
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
            coro = _send_node_key(my_master.key, data['identifier'], port,
                                    local_name, scheme, uri, cafile)
        else:
            coro = _send_lumen_key(my_master.key, data['identifier'], port,
                                    local_name, scheme, uri, cafile,
                                    data['lumen_params'])
        try:
            name = await coro
            success = True
        except errors.ApiError as e:
            error_msg = str(e)
            name = data['identifier']
            success = False

        # remove the node if it already exists, since we are creating a new API key
        # this will have the effect of expiring the old key
        db.query(Master). \
            filter(Master.type == my_master.type). \
            filter(Master.name == name).delete()
        my_master.name = name
        db.add(my_master)
        db.commit()
        if success:
            return web.json_response({"name": my_master.name})
        else:
            return web.json_response({"error": error_msg}, status=400) 
    except (ValueError, KeyError) as e:
        # Unlikely to happen, maybe if the request is malformed
        db.delete(my_master)
        db.commit()
        raise web.HTTPBadRequest(reason="Cannot add master: [%s]" % str(e))
  
async def _send_node_key(key: str,
                         identifier: str,
                         local_port: int,
                         local_name: str,
                         local_scheme: str,
                         local_uri: str,
                         cafile: str) -> str:
    # if the identifier is an IP address or a domain name, turn it into a URL
    if identifier.startswith("http://") or identifier.startswith("https://"):
        url = identifier
    else:
        url = await detect_url(identifier, 443)
        if url is None:
            raise errors.ApiError(f"cannot connect to {identifier}, try using a full URL like http(s)://...")
    
    ##NOTE: The key is not needed to access /followers but the parameter is required by TcpSession
    # This is the only route that is not authenticated by an API key
    session = TcpSession(url, key, cafile)
    params = {'key': key,
              'port': local_port,
              'name': local_name,
              'base_uri': local_uri,
              'scheme': local_scheme}
    if cafile != "":
        params["name_is_host"] = 1
    resp = await session.post(EndPoints.follower, json=params)
    await session.close()
    return resp['name']


async def _send_lumen_key(key: str,
                          identifier: str,
                          local_port: int,
                          local_name: str,
                          local_scheme: str,
                          local_uri: str,
                          cafile: str,
                          lumen_params: Dict) -> str:
    # if the identifier is an IP address or a domain name, turn it into a URL
    if not identifier.startswith("http"):
        url = await detect_url(identifier + "/lumen")
        if url is None:
            raise errors.ApiError(f"cannot connect to {identifier}, try using a full URL like http(s)://...")
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
    finally:
        await session.close()
    return identifier

### END: Helper Functions for Add ###


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
            raise web.HTTPBadRequest(reason="cannot delete yourself, this would lock you out of the node")

        db.delete(master)
    except (KeyError, ValueError):
        raise web.HTTPBadRequest(reason="specify name and master_type")
    except exc.NoResultFound:
        raise web.HTTPNotFound(reason="%s [%s] is not a master of node [%s]" % (str_master_type, name, node_name))
    db.commit()
    return web.Response(text="ok")
