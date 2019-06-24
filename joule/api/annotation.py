from typing import List, TYPE_CHECKING, Dict, Optional

from joule import errors
from .session import BaseSession


class Annotation:
    """
    API Annotation model.

    Parameters:
       title: (string)
       content: (string)
    """

    def __init__(self, title: str, content: str, stream_id: int, start: int, end: int):
        self.title = title
        self.content = content
        self.stream_id = stream_id
        self.start = start
        self.end = end


def from_json(json) -> Annotation:
    return Annotation(json['title'], json['content'], json['stream_id'], )


async def annotation_create(session: BaseSession, stream, title, start, content="", end=None) -> Annotation:
    data = {"stream_id": stream,
            "title": title,
            "content": parameters,
            "start": start,
            "end": end}
    resp = await session.post("/annotation.json", json=data)
    if master_type == "user":
        return Master(master_type, resp["name"], resp["key"])
    else:
        return Master(master_type, resp["name"], "omitted")


async def annotation_delete(session: BaseSession, master_type: str, name: str):
    data = {"master_type": master_type,
            "name": name}
    await session.delete("/master.json", params=data)

async def annotation_update(session: BaseSession, annotation:Annotation):
    pass

async def annotation_get(session: BaseSession, stream: Stream, start:int, end:int = None):
    pass
