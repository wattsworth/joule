import aiodns
import aiohttp
from aiohttp import web
from sqlalchemy.orm import Session

from joule.models import Follower
from joule.api import TcpNode

async def index(request: web.Request):
    db: Session = request.app["db"]
    followers = db.query(Follower)
    return web.json_response([f.to_json() for f in followers])


# Note: this is covered with e2e tests
async def add(request: web.Request):  # pragma: no cover
    """
    Called by a Joule node to allow *this* node to control it
    Parameters:
        key(str): the API key to use
        location(str): (optional) specify the URL of the follower
        port(int): specify the port Joule is using on the follower

    """
    db: Session = request.app["db"]
    cafile = request.app["cafile"]
    if request.content_type != 'application/json':
        return web.Response(text='content-type must be application/json', status=400)
    body = await request.json()

    try:
        key = body["key"]
        port = body["port"]
        scheme = body["scheme"]
        if "name_is_host" in body:
            location = scheme+"://" + body["name"] + ":" + str(port)
        else:
            location = scheme+"://" + request.remote + ":" + str(port)
        try:
            node = TcpNode("new_follower", location, key, cafile)
            info = await node.info()
            await node.close()
            follower_name = info.name
        except aiohttp.ClientError:
            return web.Response(text="no route to node", status=400)
        except ValueError as e:
            return web.Response(text=str(e), status=400)
        follower = Follower(key=key, location=location,
                            name=follower_name)
        # update the follower if this is a repeat
        db.query(Follower).filter(Follower.location == follower.location).delete()
        db.add(follower)
        db.commit()
    except KeyError as e:
        return web.Response(text="Invalid request, missing [%s]" % str(e), status=400)
    except ValueError as e:
        return web.Response(text="Invalid request, bad argument format", status=400)
    return web.json_response(data={'name': request.app["name"]})


async def delete(request: web.Request):
    """
    Remove the specified node from the list of followers
    """
    db: Session = request.app["db"]
    try:
        name = request.query["name"]
        db.query(Follower).filter(name == name).delete()
        db.commit()
    except KeyError:
        return web.Response(text="specify name to remove", status=400)
    return web.Response(text="OK")
