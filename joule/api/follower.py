from typing import List

from . import node
from .session import BaseSession


def from_json(json) -> node.TcpNode:
    return node.create_tcp_node(json['name'], json['location'], json['key'])


async def follower_list(session: BaseSession) -> List[node.TcpNode]:
    resp = await session.get("/followers.json")
    return [from_json(item) for item in resp]


async def follower_delete(session: BaseSession, name: str):
    data = {"name": name}
    await session.delete("/follower.json", params=data)
