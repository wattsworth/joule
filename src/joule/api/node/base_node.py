from typing import Union, List, Optional, Dict
from asyncio import AbstractEventLoop
import sqlalchemy

from .node_info import NodeInfo

from joule.api.session import BaseSession, TcpSession

from joule.api.folder import (Folder,
                              folder_root,
                              folder_get,
                              folder_move,
                              folder_delete,
                              folder_update)

from joule.api.module import (Module,
                              module_get,
                              module_list,
                              module_logs)

from joule.api.data_stream import (DataStream,
                                   DataStreamInfo,
                                   data_stream_get,
                                   data_stream_update,
                                   data_stream_move,
                                   data_stream_delete,
                                   data_stream_create,
                                   data_stream_info,
                                   data_stream_annotation_delete)

from joule.api.event_stream import (EventStream,
                                    EventStreamInfo,
                                    event_stream_get,
                                    event_stream_update,
                                    event_stream_move,
                                    event_stream_delete,
                                    event_stream_create,
                                    event_stream_info,
                                    event_stream_write,
                                    event_stream_read,
                                    event_stream_remove)
from joule.api.event import Event

from joule.api.data import (data_write,
                            data_read,
                            data_read_array,
                            data_subscribe,
                            data_delete,
                            data_intervals,
                            data_consolidate,
                            data_drop_decimations,
                            data_decimate)

from joule.api.proxy import (proxy_list,
                             proxy_get,
                             Proxy)

from joule.api.master import (master_add,
                              master_delete,
                              master_list,
                              Master)

from joule.api.annotation import (annotation_create,
                                  annotation_delete,
                                  annotation_update,
                                  annotation_get,
                                  annotation_info,
                                  Annotation,
                                  AnnotationInfo)

from joule.api.db import (db_connect,
                          db_connection_info)

from joule.models.pipes import Pipe
from joule.utilities import ConnectionInfo


class BaseNode:

    def __init__(self, name: str,
                 session: BaseSession):
        self.name = name
        self.session = session
        # configured in child implementations
        self.url = "<unset>"

    async def close(self):
        await self.session.close()

    async def info(self) -> NodeInfo:
        resp = await self.session.get("/version.json")
        db_info = await self.session.get("/dbinfo")
        return NodeInfo(version=resp["version"], name=resp["name"], path=db_info['path'],
                        size_other=db_info["other"], size_reserved=db_info["reserved"],
                        size_free=db_info["free"], size_db=db_info["size"])

    # Folder actions

    async def folder_root(self) -> Folder:
        return await folder_root(self.session)

    async def folder_get(self,
                         folder: Union[Folder, str, int]) -> Folder:
        return await folder_get(self.session, folder)

    async def folder_move(self,
                          source: Union[Folder, str, int],
                          destination: Union[Folder, str, int]) -> None:
        await folder_move(self.session, source, destination)

    async def folder_update(self,
                            folder: Folder) -> None:
        await folder_update(self.session, folder)

    async def folder_delete(self,
                            folder: Union[Folder, str, int],
                            recursive: bool = False) -> None:
        await folder_delete(self.session, folder, recursive)

    # DataStream actions

    async def data_stream_get(self,
                              stream: Union[DataStream, str, int]) -> DataStream:
        return await data_stream_get(self.session, stream)

    async def data_stream_move(self,
                               stream: Union[DataStream, str, int],
                               folder: Union[Folder, str, int]) -> None:
        return await data_stream_move(self.session, stream, folder)

    async def data_stream_update(self,
                                 stream: DataStream) -> None:
        return await data_stream_update(self.session,
                                        stream)

    async def data_stream_delete(self,
                                 stream: Union[DataStream, str, int]) -> None:
        await data_stream_delete(self.session, stream)

    async def data_stream_create(self,
                                 stream: DataStream,
                                 folder: Union[Folder, str, int]) -> DataStream:
        return await data_stream_create(self.session, stream, folder)

    async def data_stream_info(self,
                               stream: Union[DataStream, str, int]) -> DataStreamInfo:
        return await data_stream_info(self.session, stream)

    async def data_stream_annotation_delete(self,
                                            stream: Union[DataStream, str, int],
                                            start: Optional[int] = None,
                                            end: Optional[int] = None):
        return await data_stream_annotation_delete(self.session, stream, start, end)

    # EventStream actions

    async def event_stream_get(self,
                               stream: Union[EventStream, str, int],
                               create: bool = False,
                               description: str = "",
                               event_fields=None) -> EventStream:
        return await event_stream_get(self.session, stream, create, description, event_fields)

    async def event_stream_move(self,
                                stream: Union[DataStream, str, int],
                                folder: Union[Folder, str, int]) -> None:
        return await event_stream_move(self.session, stream, folder)

    async def event_stream_update(self,
                                  stream: EventStream) -> None:
        return await event_stream_update(self.session,
                                         stream)

    async def event_stream_delete(self,
                                  stream: Union[EventStream, str, int]) -> None:
        await event_stream_delete(self.session, stream)

    async def event_stream_create(self,
                                  stream: EventStream,
                                  folder: Union[Folder, str, int]) -> EventStream:
        return await event_stream_create(self.session, stream, folder)

    async def event_stream_info(self,
                                stream: Union[EventStream, str, int]) -> EventStreamInfo:
        return await event_stream_info(self.session, stream)

    async def event_stream_write(self,
                                 stream: Union[EventStream, str, int],
                                 events: List[Event]) -> List[Event]:
        return await event_stream_write(self.session, stream, events)

    async def event_stream_read(self,
                                stream: Union[EventStream, str, int],
                                start: Optional[int] = None,
                                end: Optional[int] = None,
                                limit: Optional[int] = None,
                                json_filter: Optional[Dict[str, str]] = None) -> List[Event]:
        return await event_stream_read(self.session, stream, start, end, limit, json_filter)

    async def event_stream_remove(self,
                                  stream: Union[EventStream, str, int],
                                  start: Optional[int] = None,
                                  end: Optional[int] = None,
                                  json_filter=None) -> None:
        return await event_stream_remove(self.session, stream, start, end, json_filter)

    # Data actions

    async def data_read(self,
                        stream: Union[DataStream, str, int],
                        start: Optional[int] = None,
                        end: Optional[int] = None,
                        max_rows: Optional[int] = None) -> Pipe:
        return await data_read(self.session, stream, start, end,
                               max_rows)

    async def data_read_array(self,
                              stream: Union[DataStream, str, int],
                              start: Optional[int] = None,
                              end: Optional[int] = None,
                              max_rows: int = 10000,
                              flatten: bool = False
                              ):
        return await data_read_array(self.session, stream, start, end, max_rows, flatten)

    def set_nilmdb_url(self, nilmdb_url):
        self.session.set_nilmdb_url(nilmdb_url)

    async def data_subscribe(self,
                             stream: Union[DataStream, str, int]) -> Pipe:
        return await data_subscribe(self.session, stream)

    async def data_intervals(self,
                             stream: Union[DataStream, str, int],
                             start: Optional[int] = None,
                             end: Optional[int] = None) -> List:
        return await data_intervals(self.session, stream, start, end)

    async def data_consolidate(self,
                               stream: Union[DataStream, str, int],
                               max_gap: int,
                               start: Optional[int] = None,
                               end: Optional[int] = None) -> List:
        return await data_consolidate(self.session, stream, start, end, max_gap)

    async def data_drop_decimations(self,
                                    stream: Union[DataStream, str, int]):
        return await data_drop_decimations(self.session, stream)

    async def data_decimate(self,
                            stream: Union[DataStream, str, int]):
        return await data_decimate(self.session, stream)

    async def data_write(self, stream: Union[DataStream, str, int],
                         start: Optional[int] = None,
                         end: Optional[int] = None) -> Pipe:
        return await data_write(self.session, stream, start, end)

    async def data_delete(self, stream: Union[DataStream, str, int],
                          start: Optional[int] = None,
                          end: Optional[int] = None) -> None:
        return await data_delete(self.session, stream, start, end)

    # Module actions

    async def module_list(self,
                          statistics: bool = False) -> List[Module]:
        return await module_list(self.session, statistics)

    async def module_get(self,
                         module: Union[Module, str, int],
                         statistics: bool = False) -> Module:
        return await module_get(self.session, module, statistics)

    async def module_logs(self,
                          module: Union[Module, str, int]) -> List[str]:
        return await module_logs(self.session, module)

    # Proxy actions

    async def proxy_list(self) -> List[Proxy]:
        return await proxy_list(self.session)

    async def proxy_get(self,
                        proxy: Union[Proxy, str, int]) -> Proxy:
        return await proxy_get(self.session, proxy)

    # Master actions

    async def master_list(self) -> List[Master]:
        return await master_list(self.session)

    async def master_delete(self, master_type: str, name: str) -> None:
        return await master_delete(self.session, master_type, name)

    async def master_add(self, master_type, identifier,
                         lumen_parameters: Optional[Dict] = None,
                         api_key=None) -> Master:
        return await master_add(self.session, master_type, identifier, lumen_parameters, api_key)

    # Follower actions
    async def follower_list(self) -> List['BaseNode']:
        pass

    async def follower_delete(self, node: Union['BaseNode', str]):
        if type(node) is not str:
            name = node.name
        else:
            name = node
        data = {"name": name}
        await self.session.delete("/follower.json", params=data)

    # Annotation actions
    async def annotation_get(self, stream: Union[int, str, DataStream],
                             start: Optional[int] = None,
                             end: Optional[int] = None) -> List[Annotation]:
        return await annotation_get(self.session, stream, start, end)

    async def annotation_create(self,
                                annotation: Annotation,
                                stream: Union[int, str, DataStream], ) -> Annotation:
        return await annotation_create(self.session,
                                       annotation, stream)

    async def annotation_delete(self,
                                annotation: Union[int, Annotation]):
        return await annotation_delete(self.session, annotation)

    async def annotation_update(self,
                                annotation: Annotation):
        return await annotation_update(self.session, annotation)

    async def annotation_info(self,
                              stream: Union[int, str, DataStream], ) -> AnnotationInfo:
        return await annotation_info(self.session, stream)

    # Database actions
    async def db_connect(self) -> sqlalchemy.engine.Engine:
        return await db_connect(self.session)

    async def db_connection_info(self) -> ConnectionInfo:
        return await db_connection_info(self.session)
