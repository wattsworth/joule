import sqlalchemy
import ipaddress
from urllib.parse import urlparse

from .session import BaseSession
from joule.utilities import connection_info
from joule.constants import EndPoints


async def db_connect(session: BaseSession) -> sqlalchemy.engine.Engine:
    conn_info = await db_connection_info(session)
    return sqlalchemy.create_engine(conn_info.to_dsn())


async def db_connection_info(session: BaseSession) -> connection_info.ConnectionInfo:
    resp = await session.get(EndPoints.db_connection)
    conn_info = connection_info.from_json(resp)
    if is_localhost(conn_info.host):
        # replace the host with the session host
        url = urlparse(session.url)
        conn_info.host = url.hostname
    return conn_info

def is_localhost(hostname) -> bool:
    if hostname == 'localhost':
        return True
    try:
        ip = ipaddress.ip_address(hostname)
        if ip.is_loopback:
            return True
    except ValueError:
        # If it's not an IP address, it might be a domain name, which is not localhost
        return False
    # It is an IP address but not a loopback address
    return False
