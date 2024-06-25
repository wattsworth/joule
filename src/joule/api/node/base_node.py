from typing import Union, List, Optional, Dict, TYPE_CHECKING


if TYPE_CHECKING:
    import sqlalchemy
    from joule.api.data_stream import DataStream
    from joule.api.event_stream import EventStream, EventStreamInfo
    from joule.api.module import Module
    from joule.api.proxy import Proxy
    from joule.api.master import Master
    from joule.api.annotation import Annotation, AnnotationInfo
    from joule.api.folder import Folder
    from joule.api.event import Event
    from joule.api.data_stream import DataStreamInfo, DataStream
    from joule.models.pipes import Pipe
    from joule.utilities import ConnectionInfo
    from joule.api.session import BaseSession
    from .node_info import NodeInfo



class BaseNode:

    def __init__(self, name: str,
                 session: 'BaseSession'):
        self.name = name
        self.session = session
        # configured in child implementations
        self.url = "<unset>"

    async def close(self):
        await self.session.close()

    async def info(self) -> 'NodeInfo':
        from .node_info import NodeInfo
        resp = await self.session.get("/version.json")
        db_info = await self.session.get("/dbinfo")
        return NodeInfo(version=resp["version"], name=resp["name"], path=db_info['path'],
                        size_other=db_info["other"], size_reserved=db_info["reserved"],
                        size_free=db_info["free"], size_db=db_info["size"])

    # Folder actions

    async def folder_root(self) -> 'Folder':
        from joule.api.folder import folder_root
        return await folder_root(self.session)

    async def folder_get(self,
                         folder: Union['Folder', str, int]) -> 'Folder':
        from joule.api.folder import folder_get
        return await folder_get(self.session, folder)

    async def folder_move(self,
                          source: Union['Folder', str, int],
                          destination: Union['Folder', str, int]) -> None:
        from joule.api.folder import folder_move
        await folder_move(self.session, source, destination)

    async def folder_update(self,
                            folder: 'Folder') -> None:
        from joule.api.folder import folder_update
        await folder_update(self.session, folder)

    async def folder_delete(self,
                            folder: Union['Folder', str, int],
                            recursive: bool = False) -> None:
        from joule.api.folder import folder_delete
        await folder_delete(self.session, folder, recursive)

    # DataStream actions

    async def data_stream_get(self,
                              stream: Union['DataStream', str, int]) -> 'DataStream':
        from joule.api.data_stream import data_stream_get
        return await data_stream_get(self.session, stream)

    async def data_stream_move(self,
                               stream: Union['DataStream', str, int],
                               folder: Union['Folder', str, int]) -> None:
        from joule.api.data_stream import data_stream_move
        return await data_stream_move(self.session, stream, folder)

    async def data_stream_update(self,
                                 stream: 'DataStream') -> None:
        from joule.api.data_stream import data_stream_update
        return await data_stream_update(self.session,
                                        stream)

    async def data_stream_delete(self,
                                 stream: Union['DataStream', str, int]) -> None:
        from joule.api.data_stream import data_stream_delete
        await data_stream_delete(self.session, stream)

    async def data_stream_create(self,
                                 stream: 'DataStream',
                                 folder: Union['Folder', str, int]) -> 'DataStream':
        from joule.api.data_stream import data_stream_create
        return await data_stream_create(self.session, stream, folder)

    async def data_stream_info(self,
                               stream: Union['DataStream', str, int]) -> 'DataStreamInfo':
        from joule.api.data_stream import data_stream_info
        return await data_stream_info(self.session, stream)

    async def data_stream_annotation_delete(self,
                                            stream: Union['DataStream', str, int],
                                            start: Optional[int] = None,
                                            end: Optional[int] = None):
        from joule.api.data_stream import data_stream_annotation_delete
        return await data_stream_annotation_delete(self.session, stream, start, end)

    # EventStream actions

    async def event_stream_get(self,
                               stream: Union['EventStream', str, int],
                               create: bool = False,
                               description: str = "",
                               chunk_duration: str = "",
                               chunk_duration_us: Optional[int] = None,
                               event_fields=None) -> 'EventStream':
        from joule.api.event_stream import event_stream_get
        return await event_stream_get(self.session, stream, create,
                                      description=description,
                                      chunk_duration=chunk_duration,
                                      chunk_duration_us=chunk_duration_us,
                                      event_fields=event_fields)

    async def event_stream_move(self,
                                stream: Union['EventStream', str, int],
                                folder: Union['Folder', str, int]) -> None:
        from joule.api.event_stream import event_stream_move
        return await event_stream_move(self.session, stream, folder)

    async def event_stream_update(self,
                                  stream: 'EventStream') -> None:
        from joule.api.event_stream import event_stream_update
        return await event_stream_update(self.session,
                                         stream)

    async def event_stream_delete(self,
                                  stream: Union['EventStream', str, int]) -> None:
        from joule.api.event_stream import event_stream_delete
        await event_stream_delete(self.session, stream)

    async def event_stream_create(self,
                                  stream: 'EventStream',
                                  folder: Union['Folder', str, int]) -> 'EventStream':
        from joule.api.event_stream import event_stream_create
        return await event_stream_create(self.session, stream, folder)

    async def event_stream_info(self,
                                stream: Union['EventStream', str, int]) -> 'EventStreamInfo':
        from joule.api.event_stream import event_stream_info
        return await event_stream_info(self.session, stream)

    async def event_stream_write(self,
                                 stream: Union['EventStream', str, int],
                                 events: List['Event']) -> List['Event']:
        from joule.api.event_stream import event_stream_write
        return await event_stream_write(self.session, stream, events)

    async def event_stream_read(self,
                                stream: Union['EventStream', str, int],
                                start: Optional[int]=None,
                                end: Optional[int]=None,
                                limit: Optional[int]=10000,
                                json_filter: Optional[Dict[str, str]]=None,
                                include_on_going_events=True) -> List['Event']:
        from joule.api.event_stream import event_stream_read
        return await event_stream_read(self.session, stream=stream,
                                       start_time=start, end_time=end,
                                       limit=limit, json_filter=json_filter,
                                       include_on_going_events=include_on_going_events)

    async def event_stream_count(self,
                                 stream: Union['EventStream', str, int],
                                 start: Optional[int] = None,
                                 end: Optional[int] = None,
                                 json_filter: Optional[Dict[str, str]] = None,
                                 include_on_going_events=True) -> int:
        from joule.api.event_stream import event_stream_count
        return await event_stream_count(self.session, stream, start, end, json_filter, include_on_going_events)

    async def event_stream_remove(self,
                                  stream: Union['EventStream', str, int],
                                  start: Optional[int] = None,
                                  end: Optional[int] = None,
                                  json_filter=None) -> None:
        from joule.api.event_stream import event_stream_remove
        return await event_stream_remove(self.session, stream, start, end, json_filter)

    # Data actions

    async def data_read(self,
                        stream: Union['DataStream', str, int],
                        start: Optional[int] = None,
                        end: Optional[int] = None,
                        max_rows: Optional[int] = None) -> 'Pipe':
        from joule.api.data import data_read
        return await data_read(self.session, stream, start, end,
                               max_rows)

    async def data_read_array(self,
                              stream: Union['DataStream', str, int],
                              start: Optional[int] = None,
                              end: Optional[int] = None,
                              max_rows: int = 10000,
                              flatten: bool = False
                              ):
        from joule.api.data import data_read_array
        return await data_read_array(self.session, stream, start, end, max_rows, flatten)

    def set_nilmdb_url(self, nilmdb_url):
        self.session.set_nilmdb_url(nilmdb_url)

    async def data_subscribe(self,
                             stream: Union['DataStream', str, int]) -> 'Pipe':
        from joule.api.data import data_subscribe
        return await data_subscribe(self.session, stream)

    async def data_intervals(self,
                             stream: Union['DataStream', str, int],
                             start: Optional[int] = None,
                             end: Optional[int] = None) -> List:
        from joule.api.data import data_intervals
        return await data_intervals(self.session, stream, start, end)

    async def data_consolidate(self,
                               stream: Union['DataStream', str, int],
                               max_gap: int,
                               start: Optional[int] = None,
                               end: Optional[int] = None) -> List:
        from joule.api.data import data_consolidate
        return await data_consolidate(self.session, stream, start, end, max_gap)

    async def data_drop_decimations(self,
                                    stream: Union['DataStream', str, int]):
        from joule.api.data import data_drop_decimations
        return await data_drop_decimations(self.session, stream)

    async def data_decimate(self,
                            stream: Union['DataStream', str, int]):
        from joule.api.data import data_decimate
        return await data_decimate(self.session, stream)

    async def data_write(self, stream: Union['DataStream', str, int],
                         start: Optional[int] = None,
                         end: Optional[int] = None,
                         merge_gap:int = 0) -> 'Pipe':
        from joule.api.data import data_write
        return await data_write(self.session, stream, start, end, merge_gap=merge_gap)

    async def data_delete(self, stream: Union['DataStream', str, int],
                          start: Optional[int] = None,
                          end: Optional[int] = None) -> None:
        from joule.api.data import data_delete
        return await data_delete(self.session, stream, start, end)

    # Module actions

    async def module_list(self,
                          statistics: bool = False) -> List['Module']:
        from joule.api.module import module_list
        return await module_list(self.session, statistics)

    async def module_get(self,
                         module: Union['Module', str, int],
                         statistics: bool = False) -> 'Module':
        from joule.api.module import module_get
        return await module_get(self.session, module, statistics)

    async def module_logs(self,
                          module: Union['Module', str, int]) -> List[str]:
        from joule.api.module import module_logs
        return await module_logs(self.session, module)

    # Proxy actions

    async def proxy_list(self) -> List['Proxy']:
        from joule.api.proxy import proxy_list
        return await proxy_list(self.session)

    async def proxy_get(self,
                        proxy: Union['Proxy', str, int]) -> 'Proxy':
        from joule.api.proxy import proxy_get
        return await proxy_get(self.session, proxy)

    # Master actions

    async def master_list(self) -> List['Master']:
        from joule.api.master import master_list
        return await master_list(self.session)

    async def master_delete(self, master_type: str, name: str) -> None:
        from joule.api.master import master_delete
        return await master_delete(self.session, master_type, name)

    async def master_add(self, master_type, identifier,
                         lumen_parameters: Optional[Dict] = None,
                         api_key=None) -> 'Master':
        from joule.api.master import master_add
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
    async def annotation_get(self, stream: Union[int, str, 'DataStream'],
                             start: Optional[int] = None,
                             end: Optional[int] = None) -> List['Annotation']:
        from joule.api.annotation import annotation_get
        return await annotation_get(self.session, stream, start, end)

    async def annotation_create(self,
                                annotation: 'Annotation',
                                stream: Union[int, str, 'DataStream'], ) -> 'Annotation':
        from joule.api.annotation import annotation_create
        return await annotation_create(self.session,
                                       annotation, stream)

    async def annotation_delete(self,
                                annotation: Union[int, 'Annotation']):
        from joule.api.annotation import annotation_delete
        return await annotation_delete(self.session, annotation)

    async def annotation_update(self,
                                annotation: 'Annotation'):
        from joule.api.annotation import annotation_update
        return await annotation_update(self.session, annotation)

    async def annotation_info(self,
                              stream: Union[int, str, 'DataStream'], ) -> 'AnnotationInfo':
        from joule.api.annotation import annotation_info
        return await annotation_info(self.session, stream)

    # Database actions
    async def db_connect(self) -> 'sqlalchemy.engine.Engine':
        from joule.api.db import db_connect
        return await db_connect(self.session)

    async def db_connection_info(self) -> 'ConnectionInfo':
        from joule.api.db import db_connection_info
        return await db_connection_info(self.session)
