from typing import Optional, List
from asyncio import AbstractEventLoop, get_event_loop

from .base_node import BaseNode
from .node_config import NodeConfig
from joule.api.session import TcpSession


class TcpNode(BaseNode):
    def __init__(self, name: str, url: str, key: str, cafile: str = "",
                 loop: Optional[AbstractEventLoop] = None):
        session = TcpSession(url, key, cafile)
        self._url = url
        self._key = key
        if loop is None:
            loop = get_event_loop()
        super().__init__(name, session, loop)
        self.url = url

    def __repr__(self):
        return "<joule.api.node.TcpNode url=\"%s\">" % self.url

    def to_config(self) -> NodeConfig:
        return NodeConfig(self.name, self.url, self._key)

    async def follower_list(self) -> List[BaseNode]:
        resp = await self.session.get("/followers.json")
        return [TcpNode(item['name'], item['location'], item['key'], self.session.cafile) for item in resp]
