from typing import List, Union, Dict

from joule import errors
from . import node, stream


class ModuleStatistics:
    def __init__(self, pid: int, create_time: int,
                 cpu_percent: float, memory_percent: float):
        self.pid = pid
        self.create_time = create_time
        self.cpu_percent = cpu_percent
        self.memory_percent = memory_percent


class Module:
    def __init__(self, id: int, name: str, description: str,
                 has_interface: bool,
                 inputs: Dict[str, stream.Stream],
                 outputs: Dict[str, stream.Stream],
                 statistics: ModuleStatistics = None):
        self.id = id
        self.name = name
        self.description = description
        self.has_interface = has_interface
        self.inputs = inputs
        self.outputs = outputs
        self.statistics = statistics

    def __repr__(self):
        return "<joule.api.Module id=%r name=%r description=%r has_interface=%r>" % (
                self.id, self.name, self.description, self.has_interface)


def from_json(json) -> Module:
    inputs = json['inputs']
    outputs = json['outputs']

    if 'statistics' in json:
        s = json['statistics']
        statistics = ModuleStatistics(s['pid'],s['create_time'],
                                      s['cpu_percent'],
                                      s['memory_percent'])
    else:
        statistics = None
    return Module(json['id'], json['name'], json['description'],
                  json['has_interface'],
                  inputs, outputs, statistics)


async def module_get(session: node.Session,
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


async def module_list(session: node.Session,
                      statistics: bool = False) -> List[Module]:
    _statistics = 1
    if not statistics:
        _statistics = 0
    resp = await session.get("/modules.json", {"statistics": _statistics})
    return [from_json(item) for item in resp]


async def module_logs(session: node.Session,
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
