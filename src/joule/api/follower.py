from typing import List, TYPE_CHECKING, Dict, Union

from .session import BaseSession
from joule.constants import EndPoints
from .node import TcpNode
if TYPE_CHECKING:
    from .node import BaseNode

async def follower_list(session: BaseSession) -> List['BaseNode']:
    resp = await session.get(EndPoints.followers)
    return [TcpNode(item['name'], item['location'], item['key'], session.cafile) for item in resp]

async def follower_delete(session: BaseSession, node: Union['BaseNode', str]) -> None:
    if type(node) is not str:
        name = node.name
    else:
        name = node
    data = {"name": name}
    await session.delete(EndPoints.follower, params=data)
