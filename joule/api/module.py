from typing import List, Union, Dict

from joule import errors
from . import stream
from .session import BaseSession


class ModuleStatistics:
    """
    API ModuleStatistics model. Received by settings statistics to ``True`` when calling :meth:`Node.module_get` or
    :meth:`Node.module_info` and should not be created directly.

    Parameters:
        pid (int): process ID
        create_time (int): process creation time in UNIX seconds
        cpu_percent (float): approximate CPU usage
        memory_percent (float): approximate memory usage
    """

    def __init__(self, pid: int, create_time: int,
                 cpu_percent: float, memory_percent: float):
        self.pid = pid
        self.create_time = create_time
        self.cpu_percent = cpu_percent
        self.memory_percent = memory_percent

    def __repr__(self):
        return "<joule.api.ModuleStatistics pid=%r create_time=%r cpu_percent=%r memory_percent=%r>" % (
            self.pid, self.create_time, self.cpu_percent, self.memory_percent)


class Module:
    """
    API Module model. See :ref:`sec-node-module-actions` for details on using the API to
    query modules. See :ref:`modules` for details on writing new modules. See :ref:`sec-modules`
    for details on adding modules to Joule. Use :meth:`Node.stream_get` to retrieve the associated stream from the path string
    in the ``inputs`` and ``outputs`` dictionaries.

    Parameters:
       id (int): unique numeric ID assigned by Joule server
       name (str): module name, must be unique
       description (str): optional field
       is_app (bool): whether the module provides a web interface
       inputs (Dict): Mapping of ``[pipe_name] = stream_path`` for module inputs
       outputs (Dict): Mapping of ``[pipe_name] = stream_path`` for output connections
       statistics (ModuleStatistics): execution statistics, may be ``None`` depending on API call parameters
    """

    def __init__(self, id: int, name: str, description: str,
                 is_app: bool,
                 inputs: Dict[str, stream.Stream],
                 outputs: Dict[str, stream.Stream],
                 statistics: ModuleStatistics = None):
        self.id = id
        self.name = name
        self.description = description
        self.is_app = is_app
        self.inputs = inputs
        self.outputs = outputs
        self.statistics = statistics

    def __repr__(self):
        return "<joule.api.Module id=%r name=%r description=%r is_app=%r>" % (
            self.id, self.name, self.description, self.is_app)


def from_json(json) -> Module:
    inputs = json['inputs']
    outputs = json['outputs']

    if 'statistics' in json:
        s = json['statistics']
        statistics = ModuleStatistics(s['pid'], s['create_time'],
                                      s['cpu_percent'],
                                      s['memory_percent'])
    else:
        statistics = None

    return Module(json['id'], json['name'], json['description'],
                  json['is_app'],
                  inputs, outputs, statistics)


async def module_get(session: BaseSession,
                     module: Union[Module, str, int],
                     statistics: bool = True) -> Module:
    _statistics = 0
    if statistics:
        _statistics = 1

    params = {"statistics": _statistics}
    if type(module) is Module:
        params["id"] = module.id
    elif type(module) is str:
        params["name"] = module
    elif type(module) is int:
        params["id"] = module
    else:
        raise errors.ApiError("Invalid module datatype. Must be Module, Name, or ID")

    resp = await session.get("/module.json", params)
    return from_json(resp)


async def module_list(session: BaseSession,
                      statistics: bool = False) -> List[Module]:
    _statistics = 1
    if not statistics:
        _statistics = 0
    resp = await session.get("/modules.json", {"statistics": _statistics})
    return [from_json(item) for item in resp]


async def module_logs(session: BaseSession,
                      module: Union[Module, str, int]) -> List[str]:
    params = {}
    if type(module) is Module:
        params["id"] = module.id
    elif type(module) is str:
        params["name"] = module
    elif type(module) is int:
        params["id"] = module
    else:
        raise errors.ApiError("Invalid module datatype. Must be Module, Name, or ID")

    return await session.get("/module/logs.json", params)
