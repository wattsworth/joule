from typing import Optional
from asyncio import AbstractEventLoop, get_event_loop

from .base_node import BaseNode
from joule.api.session import UnixSession


class UnixNode(BaseNode):

    def __init__(self, name: str, path: str,
                 loop: Optional[AbstractEventLoop] = None):
        self._path = path
        session = UnixSession(path)
        if loop is None:
            loop = get_event_loop()
        super().__init__(name, session, loop)

    def __repr__(self):
        return "<joule.api.node.UnixNode path=\"%s\">" % self._path
