from aiohttp.web import middleware, HTTPForbidden
from sqlalchemy.orm import Session
from joule.models import Master


def authorize(exemptions=None):
    if exemptions is None:
        exemptions = []

    @middleware
    async def _authorize(request, handler):
        db: Session = request.app["db"]
        # OK, exempt request
        if [request.method, request.path] in exemptions:
            return await handler(request)
        # Anything over the UNIX socket is ok
        # Check if the remote field is empty:
        if request.remote == "":
            return await handler(request)
        # Missing Key
        if 'X-API-KEY' not in request.headers:
            raise HTTPForbidden()
        key = request.headers['X-API-KEY']
        # Invalid Key
        if (db.query(Master).
                filter(Master.key == key).
                count() != 1):
            raise HTTPForbidden
        # OK, valid key
        return await handler(request)

    return _authorize
