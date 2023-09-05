from typing import Union, List, Optional, TYPE_CHECKING
from dataclasses import dataclass

from joule import errors
from .session import BaseSession

#if TYPE_CHECKING:
from .data_stream import DataStream


class Annotation:
    """
    API Annotation model. See :ref:`sec-node-annotation-actions` for details on using the API to
    manipulate annotations. Annotations are associated with streams and may either coverage a range
    of data or a single event. If **end** is ``None`` the annotation marks an event, otherwise
    it marks a range.

    Parameters:
       title (string): annotation title
       content (string): additional description (optional)
       start (int): Unix microsecond timestamp
       end (int): specify for range annotation, omit for event annotation
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

    def __eq__(self, other: 'Annotation'):
        if self.title != other.title:
            return False
        if self.content != other.content:
            return False
        if self.start != other.start:
            return False
        if self.end != other.end:
            return False
        return True

    def to_json(self):
        return {
            'title': self.title,
            'start': self.start,
            'end': self.end,
            'content': self.content,
            'id': self.id
        }


@dataclass
class AnnotationInfo:
    start: int
    end: int
    count: int


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
                            stream: Union[int, str, 'DataStream'], ) -> Annotation:
    from .data_stream import DataStream

    data = {"title": annotation.title,
            "content": annotation.content,
            "start": annotation.start,
            "end": annotation.end}
    if type(stream) is DataStream:
        data["stream_id"] = stream.id
    elif type(stream) is int:
        data["stream_id"] = stream
    elif type(stream) is str:
        data["stream_path"] = stream
    else:
        raise errors.ApiError("Invalid stream datatype. Must be DataStream, Path, or ID")

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


async def annotation_info(session: BaseSession,
                          stream: Union['DataStream', str, int]):
    data = {}
    if type(stream) is DataStream:
        data["stream_id"] = stream.id
    elif type(stream) is int:
        data["stream_id"] = stream
    elif type(stream) is str:
        data["stream_path"] = stream
    else:
        raise errors.ApiError("Invalid stream datatype. Must be DataStream, Path, or ID")

    json = await session.get("/annotations/info.json", data)
    return AnnotationInfo(**json)


async def annotation_get(session: BaseSession,
                         stream: Union['DataStream', str, int],
                         start: Optional[int],
                         end: Optional[int]) -> List[Annotation]:
    from .data_stream import DataStream

    data = {}
    if start is not None:
        data["start"] = start
    if end is not None:
        data["end"] = end

    if type(stream) is DataStream:
        data["stream_id"] = stream.id
    elif type(stream) is int:
        data["stream_id"] = stream
    elif type(stream) is str:
        data["stream_path"] = stream
    else:
        raise errors.ApiError("Invalid stream datatype. Must be DataStream, Path, or ID")

    json = await session.get("/annotations.json", data)

    annotations = []
    for item in json:
        annotations.append(from_json(item))
    return annotations
