import aiodns
import asyncio
from aiohttp import web
from sqlalchemy.orm import Session

from joule.models import Follower


async def index(request: web.Request):
    db: Session = request.app["db"]
    followers = db.query(Follower)
    return web.json_response([f.to_json for f in followers])


async def add(request: web.Request):
    """
    Called by a Joule node to allow *this* node to control it
    Parameters:
        key(str): the API key to use
        location(str): (optional) specify the URL of the follower
        port(int): specify the port Joule is using on the follower

    """
    db: Session = request.app["db"]
    try:
        key = request.query["key"]
        port = request.query["port"]
        if "location" in request.query:
            location = request.query["location"]
        else:  # use the origin of this request
            location = request.remote
            try:
                # try to find a domain name instead of IP address
                resolver = aiodns.DNSResolver()
                resolved = await resolver.gethostbyaddr(location)
                location = resolved.name
            except aiodns.error.DNSError:
                pass  # reverse lookup failed, use the IP address
        location = location + ":" + port
        follower = Follower(key=key, location=location)
        db.add(follower)
        db.commit()
    except KeyError as e:
        return web.Response(text="Invalid request, missing [%s]" % str(e), status=400)
    except ValueError as e:
        return web.Response(text="Invalid request, bad argument format", status=400)
    return web.Response(text="OK", status=200)
