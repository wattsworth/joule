from typing import Union, List, Optional, TYPE_CHECKING

from joule import errors
from .session import BaseSession

if TYPE_CHECKING:
    from .stream import Stream


class Annotation:
    """
    API Annotation model.

    Parameters:
       title: (string)
       content: (string) optional
       start: (int) Unix microsecond timestamp
       end: (int) specify for range annotation, omit for event annotation
    """

    def __init__(self, title: str,
                 start: int,
                 end: Optional[int] = None,
                 content: str = ""):
        self.id = None
        self.title = title
        self.content = content
        self.stream_id = None
        self.start = start
        self.end = end


def from_json(json) -> Annotation:
    annotation = Annotation(title=json['title'],
                            start=json['start'],
                            end=json['end'],
                            content=json['content'])
    annotation.id = json["id"]
    annotation.stream_id = json["stream_id"]
    return annotation


async def annotation_create(session: BaseSession,
                            annotation: Annotation,
                            stream: Union[int, str, 'Stream'], ) -> Annotation:
    from .stream import Stream

    data = {"title": annotation.title,
            "content": annotation.content,
            "start": annotation.start,
            "end": annotation.end}
    if type(stream) is Stream:
        data["stream_id"] = stream.id
    elif type(stream) is int:
        data["stream_id"] = stream
    elif type(stream) is str:
        data["stream_path"] = stream
    else:
        raise errors.ApiError("Invalid stream datatype. Must be Stream, Path, or ID")

    json = await session.post("/annotation.json", json=data)
    return from_json(json)


async def annotation_delete(session: BaseSession,
                            annotation: Union[int, Annotation]):
    data = {}
    if type(annotation) is Annotation:
        data["id"] = annotation.id
    elif type(annotation) is int:
        data["id"] = annotation

    await session.delete("/annotation.json", params=data)


async def annotation_update(session: BaseSession,
                            annotation: Annotation):
    data = {"id": annotation.id,
            "title": annotation.title,
            "content": annotation.content,
            }
    json = await session.put("/annotation.json", json=data)
    return from_json(json)


async def annotation_get(session: BaseSession,
                         stream: Union['Stream', str, int],
                         start: Optional[int],
                         end: Optional[int]) -> List[Annotation]:
    from .stream import Stream

    data = {}
    if start is not None:
        data["start"] = start
    if end is not None:
        data["end"] = end

    if type(stream) is Stream:
        data["stream_id"] = stream.id
    elif type(stream) is int:
        data["stream_id"] = stream
    elif type(stream) is str:
        data["stream_path"] = stream
    else:
        raise errors.ApiError("Invalid stream datatype. Must be Stream, Path, or ID")

    json = await session.get("/annotations.json", data)

    annotations = []
    for item in json:
        annotations.append(from_json(item))
    return annotations
