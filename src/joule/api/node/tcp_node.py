from typing import List
from .base_node import BaseNode
from .node_config import NodeConfig
from joule.api.session import TcpSession
from joule.constants import EndPoints

class TcpNode(BaseNode):
    def __init__(self, name: str, url: str, key: str, cafile: str = ""):
        session = TcpSession(url, key, cafile)
        self._url = url
        self._key = key
        super().__init__(name, session)
        self.url = url

    def __repr__(self):
        return "<joule.api.node.TcpNode url=\"%s\">" % self.url

    def to_config(self) -> NodeConfig:
        return NodeConfig(self.name, self.url, self._key)

