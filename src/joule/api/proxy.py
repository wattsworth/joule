from typing import List, Union
import yarl

from joule import errors
from .session import BaseSession


class Proxy:
    """
    API Proxy model. See :ref:`sec-node-proxy-actions` for details on using the API to
    query proxies.

    Parameters:
       id (int): unique numeric ID assigned by Joule server
       name (str): proxy name
       target_url (str): URL to proxy
    """

    def __init__(self, id: int, name: str,
                 target_url: str):
        self.id = id
        self.name = name
        self.target_url = target_url

    def __repr__(self):
        return "<joule.api.Proxy id=%r name=%r target_url=%r>" % (
            self.id, self.name, self.target_url)


def from_json(json: dict) -> Proxy:
    return Proxy(id=json['id'], name=json['name'], target_url=json['url'])


async def proxy_get(session: BaseSession,
                    proxy: Union[Proxy, str, int]) -> Proxy:
    params = {}
    if type(proxy) is Proxy:
        params["id"] = proxy.id
    elif type(proxy) is str:
        params["name"] = proxy
    elif type(proxy) is int:
        params["id"] = proxy
    else:
        raise errors.ApiError("Invalid proxy datatype. Must be Proxy, Name, or ID")

    resp = await session.get("/proxy.json", params)
    return from_json(resp)


async def proxy_list(session: BaseSession) -> List[Proxy]:
    resp = await session.get("/proxies.json")
    return [from_json(item) for item in resp]
