from typing import Union

from joule import errors
from .folder_type import Folder
from .session import BaseSession
from .stream import from_json as stream_from_json


def from_json(json) -> Folder:
    streams = [stream_from_json(val) for val in json['streams']]
    children = [from_json(val) for val in json['children']]
    my_folder = Folder()
    my_folder.id = json['id']
    my_folder.name = json['name']
    my_folder.description = json['description']
    my_folder.children = children
    my_folder.streams = streams
    my_folder.locked = json['locked']
    return my_folder


async def folder_root(session: BaseSession) -> Folder:
    resp = await session.get("/streams.json")
    return from_json(resp)


async def folder_move(session: BaseSession,
                      source: Union[Folder, str, int],
                      destination: Union[Folder, str, int]) -> None:
    data = {}

    if type(source) is Folder:
        data["src_id"] = source.id
    elif type(source) is int:
        data["src_id"] = source
    elif type(source) is str:
        data["src_path"] = source
    else:
        raise errors.ApiError("Invalid source datatype. Must be Folder, Path, or ID")

    if type(destination) is Folder:
        data["dest_id"] = destination.id
    elif type(destination) is int:
        data["dest_id"] = destination
    elif type(destination) is str:
        data["dest_path"] = destination
    else:
        raise errors.ApiError("Invalid destination datatype. Must be Folder, Path, or ID")

    await session.put("/folder/move.json", data)


async def folder_delete(session: BaseSession,
                        folder: Union[Folder, str, int],
                        recursive: bool = False) -> None:
    _recursive = 0
    if recursive:
        _recursive = 1
    data = {"recursive": _recursive}

    if type(folder) is Folder:
        data["id"] = folder.id
    elif type(folder) is int:
        data["id"] = folder
    elif type(folder) is str:
        data["path"] = folder
    else:
        raise errors.ApiError("Invalid folder datatype. Must be Folder, Path, or ID")

    await session.delete("/folder.json", data)


async def folder_update(session: BaseSession,
                        folder: Folder) -> None:
    return await session.put("/folder.json", {"id": folder.id,
                                              "folder": folder.to_json()})


async def folder_get(session: BaseSession,
                     folder: Union[Folder, str, int]) -> Folder:
    params = {}
    if type(folder) is Folder:
        params["id"] = folder.id
    elif type(folder) is int:
        params["id"] = folder
    elif type(folder) is str:
        params["path"] = folder
    else:
        raise errors.ApiError("Invalid folder datatype. Must be Folder, Path, or ID")

    resp = await session.get("/folder.json", params)
    return from_json(resp)
