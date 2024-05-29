from aiohttp import web
from joule.utilities import ConnectionInfo
from joule.models.supervisor import Supervisor
from joule.models import DataStore, EventStore
from sqlalchemy.orm import Session

module_connection_info = web.AppKey("module-connection-info", ConnectionInfo)
supervisor = web.AppKey("supervisor", Supervisor)
data_store = web.AppKey("data-store", DataStore)
event_store = web.AppKey("event-store", EventStore)
db = web.AppKey("db", Session)
base_uri = web.AppKey("base-uri", str)
name = web.AppKey("name", str)
port = web.AppKey("port", int)
scheme = web.AppKey("scheme", str)
cafile = web.AppKey("cafile", str)
remote_ip = web.AppKey("remote-ip", str)  # set by middleware but not used?


