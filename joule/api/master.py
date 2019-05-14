from typing import List, TYPE_CHECKING, Dict, Optional

from joule import errors
from .session import BaseSession


class Master:
    """
    API Master model. See :ref:`sec-node-master-actions` for details on using the API to
    manage master users and nodes.

    Parameters:
       master_type (str): one of [user|joule_node|lumen_node]
       name: unique identifier for the master (username, node name, or URL)
    """

    def __init__(self, master_type: str, name: str, key: str):
        self.master_type = master_type
        self.name = name
        self.key = key


def from_json(json) -> Master:
    return Master(json['type'], json['name'], "omitted")


async def master_add(session: BaseSession, master_type: str,
                     identifier: str, parameters: Optional[Dict] = None) -> Master:
    data = {"master_type": master_type,
            "identifier": identifier,
            "lumen_params": parameters}
    resp = await session.post("/master.json", json=data)
    if master_type == "user":
        return Master(master_type, resp["name"], resp["key"])
    else:
        return Master(master_type, resp["name"], "omitted")


async def master_delete(session: BaseSession, master_type: str, name: str):
    data = {"master_type": master_type,
            "name": name}
    await session.delete("/master.json", params=data)


async def master_list(session: BaseSession) -> List[Master]:
    resp = await session.get("/masters.json")
    return [from_json(item) for item in resp]
