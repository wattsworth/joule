from aiohttp.web import middleware, HTTPForbidden, HTTPBadRequest
from sqlalchemy.orm import Session
import logging
from sqlalchemy.exc import SQLAlchemyError
from joule.models import Master

log = logging.getLogger('joule')


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


@middleware
async def sql_rollback(request, handler):
    db: Session = request.app["db"]
    try:
        return await handler(request)
    except SQLAlchemyError as e:
        log.warning("Invalid HTTP request: %s", e)
        db.rollback()
        raise HTTPBadRequest
