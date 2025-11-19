from aiohttp import web
from joule.utilities import ConnectionInfo
from joule.models.supervisor import Supervisor
from joule.models import DataStore, EventStore
from joule.models.data_movement.importing.importer_manager import ImporterManager
from sqlalchemy.orm import Session
import uuid as uuid_type
import asyncio

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
# globally unique ID for a node, automatically generated
# used to identify where data originated when copying between nodes
uuid = web.AppKey("uuid", uuid_type.UUID)
importer_manager = web.AppKey("importer_manager",ImporterManager)
uploaded_archives_dir = web.AppKey("uploaded_archives_dir", str)

