import aiodns
import aiohttp
from aiohttp import web
from sqlalchemy.orm import Session

from joule.models import Follower
from joule.api import TcpNode
from joule import app_keys
from joule.errors import ApiError

async def index(request: web.Request):
    db: Session = request.app[app_keys.db]
    followers = db.query(Follower)
    return web.json_response([f.to_json() for f in followers])

async def add(request: web.Request):
    """
    Called by a Joule node to allow *this* node to control it
    Parameters:
        key(str): the API key to use
        base_uri(str): (optional) specify the URL of the follower
        port(int): specify the port Joule is using on the follower

    """
    db: Session = request.app[app_keys.db]
    cafile = request.app[app_keys.cafile]
    if request.content_type != 'application/json':
        raise web.HTTPBadRequest(reason='content-type must be application/json')
    body = await request.json()

    try:
        key = body["key"]
        port = body["port"]
        scheme = body["scheme"]
        base_uri = body["base_uri"]
        # figure out the correct location of the follower
        if "name_is_host" in body:
            remote_host = body["name"]
        elif "X-Forwarded-For" in request.headers: # received from a reverse proxy
            remote_host = request.headers["X-Forwarded-For"]
        elif request.remote: # direct connection to built-in HTTP server
            remote_host = request.remote
        else:
            raise web.HTTPBadRequest(reason="could not determine remote host, specify with X-Forwarded-For if using a reverse proxy")
        location = scheme+"://" + remote_host + ":" + str(port) + base_uri
        
        node = TcpNode("new_follower", location, key, cafile)
        try:
            info = await node.info()
            follower_name = info.name
        except (aiohttp.ClientError, ApiError):
            raise web.HTTPBadRequest(reason=f"no route to node at {location}")
        finally:
            await node.close()
        follower = Follower(key=key, location=location,
                            name=follower_name)
        # update the follower if this is a repeat
        db.query(Follower).filter(Follower.location == follower.location).delete()
        db.add(follower)
        db.commit()
    except KeyError as e:
        raise web.HTTPBadRequest(reason="Invalid request, missing [%s]" % str(e))
    except ValueError as e:
        raise web.HTTPBadRequest(reason="Invalid request, bad argument format")
    return web.json_response(data={'name': request.app[app_keys.name]})


async def delete(request: web.Request):
    """
    Remove the specified node from the list of followers
    """
    db: Session = request.app[app_keys.db]
    try:
        name = request.query["name"]
        # if the name is not in the database return 404
        if db.query(Follower).filter(Follower.name == name).count() == 0:
            raise web.HTTPNotFound(reason="follower not found")
        db.query(Follower).filter(name == name).delete()
        db.commit()
    except KeyError:
        raise web.HTTPBadRequest(reason="specify name to remove")
    return web.Response(text="OK")
