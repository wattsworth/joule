from typing import List, TYPE_CHECKING
from .session import BaseSession

if TYPE_CHECKING:
    from .node import TcpNode, BaseNode


async def follower_list(session: BaseSession) -> List['BaseNode']:
    resp = await session.get("/followers.json")
    return [TcpNode(item['name'], item['location'], item['key'], session.cafile) for item in resp]


async def follower_delete(session: BaseSession, node):
    if type(node) is not str:
        name = node.name
    else:
        name = node
    data = {"name": name}
    await session.delete("/follower.json", params=data)
