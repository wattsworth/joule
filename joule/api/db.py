import sqlalchemy
from urllib.parse import urlparse

from .session import BaseSession
from joule.utilities import connection_info


async def db_connect(session: BaseSession) -> sqlalchemy.engine.Engine:
    resp = await session.get("/db/connection.json")
    conn_info = connection_info.from_json(resp)
    # replace the host with the session host
    url = urlparse(session.url)
    conn_info.host = url.hostname
    return sqlalchemy.create_engine(conn_info.to_dsn())


async def db_connection_info(session: BaseSession) -> connection_info.ConnectionInfo:
    resp = await session.get("/db/connection.json")
    return connection_info.from_json(resp)
