from typing import Optional, List
from asyncio import AbstractEventLoop, get_event_loop

from .base_node import BaseNode
from .tcp_node import TcpNode
from joule.api.session import UnixSession


class UnixNode(BaseNode):

    def __init__(self, name: str, path: str, cafile: str = "",
                 loop: Optional[AbstractEventLoop] = None):
        self._path = path
        session = UnixSession(path, cafile)
        if loop is None:
            loop = get_event_loop()
        super().__init__(name, session, loop)
        self.url = "http://joule.localhost"

    def __repr__(self):
        return "<joule.api.node.UnixNode path=\"%s\">" % self._path

    async def follower_list(self) -> List[BaseNode]:
        resp = await self.session.get("/followers.json")
        return [TcpNode(item['name'], item['location'], item['key'], self.session.cafile) for item in resp]