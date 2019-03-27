from typing import List

from joule import errors
from . import node


class Master:
    def __init__(self, master_type: str, name: str):
        self.master_type = master_type
        self.name = name


def from_json(json) -> Master:
    return Master(json['type'], json['name'])


async def master_add(session: node.Session, master_type: str, identifier: str):
    data = {"master_type": master_type,
            "identifier": identifier}
    try:
        resp = await session.post("/master.json", json=data)
        if master_type == "user":
            return node.NodeConfig(resp["name"], resp["url"], resp["key"])
        else:
            return resp["name"]
    except errors.ApiError as e:
        if "lumen" in str(e):
            print("this is a lumen node, need e-mail/password")


async def master_delete(session: node.Session, master_type: str, name: str):
    data = {"master_type": master_type,
            "name": name}
    await session.delete("/master.json", params=data)


async def master_list(session: node.Session) -> List[Master]:
    resp = await session.get("/masters.json")
    return [from_json(item) for item in resp]
