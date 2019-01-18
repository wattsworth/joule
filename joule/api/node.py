from typing import Union, List, Optional
import numpy as np
import asyncio
from .session import Session

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

from joule.api.stream import (Stream,
                              StreamInfo,
                              stream_get,
                              stream_update,
                              stream_move,
                              stream_delete,
                              stream_create,
                              stream_info)

from joule.api.data import (data_write,
                            data_read,
                            data_delete)

from joule.models.pipes import Pipe


class Node:
    def __init__(self, url: str, loop: asyncio.AbstractEventLoop):
        self.session = Session(url)
        self.loop = loop

    async def close(self):
        await self.session.close()

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
                            recursive: bool) -> None:
        await folder_delete(self.session, folder, recursive)

    # Stream actions

    async def stream_get(self,
                         stream: Union[Stream, str, int]) -> Stream:
        return await stream_get(self.session, stream)

    async def stream_move(self,
                          stream: Union[Stream, str, int],
                          folder: Union[Folder, str, int]) -> None:
        return await stream_move(self.session, stream, folder)

    async def stream_update(self,
                            stream: Stream) -> None:
        return await stream_update(self.session,
                                   stream)

    async def stream_delete(self,
                            stream: Union[Stream, str, int]) -> None:
        await stream_delete(self.session, stream)

    async def stream_create(self,
                            stream: Stream,
                            folder: Union[Folder, str, int]) -> Stream:
        return await stream_create(self.session, stream, folder)

    async def stream_info(self,
                          stream: Union[Stream, str, int]) -> StreamInfo:
        return await stream_info(self.session, stream)

    # Data actions

    async def data_read(self,
                        stream: Union[Stream, str, int],
                        start: Optional[int] = None,
                        end: Optional[int] = None,
                        max_rows: Optional[int] = None) -> Pipe:
        return await data_read(self.session, self.loop, stream, start, end,
                               max_rows)

    async def data_write(self, stream: Union[Stream, str, int],
                         start: Optional[int] = None,
                         end: Optional[int] = None) -> Pipe:
        return await data_write(self.session, self.loop, stream, start, end)

    async def data_delete(self, stream: Union[Stream, str, int],
                          start: Optional[int] = None,
                          end: Optional[int] = None) -> List[np.ndarray]:
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
