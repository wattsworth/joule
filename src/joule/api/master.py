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
                     identifier: str, parameters: Optional[Dict] = None,
                     api_key: Optional[str] = None) -> Master:
    data = {"master_type": master_type,
            "identifier": identifier,
            "lumen_params": parameters,
            "api_key": api_key}
    try:
        resp = await session.post("/master.json", json=data)
    except errors.ApiError as e:
        if "cannot contact node at" in str(e) and master_type == 'lumen':
            msg = str(e).split("[422]")[0]
            url = msg.split("at")[1]

            print("#############################################")
            print(f"WARNING: Lumen reports that it could not connect to this Joule node with URL <<{url}>>")
            print("\tYou must update this URL to the correct value in the Lumen web interface ")
            print("\tbefore you can use Lumen to access this node")
            print("#############################################")
        else:
            raise e
    if master_type == "user":
        return Master(master_type, identifier, resp["key"])
    else:
        return Master(master_type, identifier, "omitted")


async def master_delete(session: BaseSession, master_type: str, name: str):
    data = {"master_type": master_type,
            "name": name}
    await session.delete("/master.json", params=data)


async def master_list(session: BaseSession) -> List[Master]:
    resp = await session.get("/masters.json")
    return [from_json(item) for item in resp]
