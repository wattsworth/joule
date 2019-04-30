from typing import List, TYPE_CHECKING

from joule import errors
from .session import BaseSession


class Master:
    def __init__(self, master_type: str, name: str, key: str):
        self.master_type = master_type
        self.name = name
        self.key = key


def from_json(json) -> Master:
    return Master(json['type'], json['name'], "omitted")


async def master_add(session: BaseSession, master_type: str,
                     identifier: str) -> Master:
    data = {"master_type": master_type,
            "identifier": identifier}
    try:
        resp = await session.post("/master.json", json=data)
        if master_type == "user":
            return Master(master_type, resp["name"], resp["key"])
        else:
            return Master(master_type, resp["name"], "omitted")
    except errors.ApiError as e:
        if "lumen" in str(e):
            print("this is a lumen node, need e-mail/password")
        raise e


async def master_delete(session: BaseSession, master_type: str, name: str):
    data = {"master_type": master_type,
            "name": name}
    await session.delete("/master.json", params=data)


async def master_list(session: BaseSession) -> List[Master]:
    resp = await session.get("/masters.json")
    return [from_json(item) for item in resp]
