from typing import Optional, Dict, Union, List
import json

from .session import BaseSession
from .folder_type import Folder
from .event import Event
from .event import from_json as event_from_json
from joule import errors


class EventStream:
    """
        API EventStream model. See :ref:`sec-node-event-stream-actions` for details on using the API to
        manipulate event streams.

        Parameters:
            name (str): stream name, must be unique in the parent
            description (str): optional field
    """

    def __init__(self, name: str = "", description: str = "", event_fields: Optional[Dict[str, str]] = None):
        self._id = None
        self.name = name
        self.description = description
        self.event_fields = self._validate_event_fields(event_fields)

    @property
    def id(self) -> int:
        if self._id is None:
            raise errors.ApiError("this is a local model with no ID. See API docs")
        return self._id

    @id.setter
    def id(self, value: int):
        self._id = value

    def to_json(self) -> Dict:
        return {
            "id": self._id,
            "name": self.name,
            "description": self.description,
            "event_fields": self.event_fields
        }

    def __repr__(self):
        return "<joule.api.EventStream id=%r name=%r description=%r>" % (
            self._id, self.name, self.description
        )

    def _validate_event_fields(self, fields: Optional[Dict[str, str]]) -> Dict[str, str]:
        # make sure values are either string or numeric
        if fields is None:
            return {}
        for field in fields:
            if fields[field] not in ['string', 'numeric']:
                raise errors.ApiError("invalid event field type, must be numeric or string")
        return fields


def from_json(json) -> EventStream:
    my_stream = EventStream()
    my_stream.id = json['id']
    my_stream.name = json['name']
    my_stream.description = json['description']
    my_stream.event_fields = json['event_fields']
    return my_stream


class EventStreamInfo:
    """
        API EventStreamInfo model. Received from :meth:`Node.event_stream_info` and should not be created directly.


        Parameters:
            start (int): timestamp in UNIX microseconds of the beginning of the first event
            end (int): timestamp in UNIX microsseconds of the end of the last data event
            event_count (int): number of events in the stream
            bytes (int): approximate size of the data on disk
            total_time (int): event stream duration in microseconds (start-end)

        """

    def __init__(self, start: Optional[int], end: Optional[int], event_count: int,
                 total_time: int = 0, bytes: int = 0):
        self.start = start
        self.end = end
        self.event_count = event_count
        self.bytes = bytes
        self.total_time = total_time

    def __repr__(self):
        return "<joule.api.EventStreamInfo start=%r end=%r events=%r, total_time=%r>" % (
            self.start, self.end, self.event_count, self.total_time)


def info_from_json(json) -> EventStreamInfo:
    if json is not None:

        return EventStreamInfo(json['start'],
                               json['end'],
                               json['event_count'],
                               json['total_time'],
                               json['bytes'])
    else:
        return EventStreamInfo(None,
                               None,
                               0,
                               0,
                               0)


async def event_stream_delete(session: BaseSession,
                              stream: Union[EventStream, str, int]) -> None:
    data = {}
    if type(stream) is EventStream:
        data["id"] = stream.id
    elif type(stream) is int:
        data["id"] = stream
    elif type(stream) is str:
        data["path"] = stream
    else:
        raise errors.ApiError("Invalid stream datatype. Must be EventStream, Path, or ID")

    await session.delete("/event.json", data)


async def event_stream_create(session: BaseSession,
                              stream: EventStream, folder: Union[Folder, str, int]) -> EventStream:
    data = {"stream": stream.to_json()}

    if type(folder) is Folder:
        data["dest_id"] = folder.id
    elif type(folder) is int:
        data["dest_id"] = folder
    elif type(folder) is str:
        data["dest_path"] = folder
    else:
        raise errors.ApiError("Invalid folder datatype. Must be Folder, Path, or ID")

    resp = await session.post("/event.json", json=data)
    return from_json(resp)


async def event_stream_info(session: BaseSession,
                            stream: Union[EventStream, str, int]) -> EventStreamInfo:
    data = {}

    if type(stream) is EventStream:
        data["id"] = stream.id
    elif type(stream) is int:
        data["id"] = stream
    elif type(stream) is str:
        data["path"] = stream
    else:
        raise errors.ApiError("Invalid stream datatype. Must be EventStream, Path, or ID")

    resp = await session.get("/event.json", data)
    return info_from_json(resp['data_info'])


async def event_stream_get(session: BaseSession,
                           stream: Union[EventStream, str, int],
                           create: bool = False,
                           description: str = "",
                           event_fields=None) -> EventStream:
    data = {}

    if type(stream) is EventStream:
        data["id"] = stream.id
    elif type(stream) is int:
        data["id"] = stream
    elif type(stream) is str:
        data["path"] = stream
    else:
        raise errors.ApiError("Invalid stream datatype. Must be EventStream, Path, or ID")

    try:
        resp = await session.get("/event.json", data)
    except errors.ApiError as e:
        # pass the error if the stream should not or cannot be created
        if not create or type(stream) is not str:
            raise e
        name = stream.split('/')[-1]
        path = '/'.join(stream.split('/')[:-1])
        event_stream = EventStream(name, description, event_fields)
        return await event_stream_create(session, event_stream, path)
    return from_json(resp)


async def event_stream_update(session: BaseSession,
                              stream: EventStream) -> None:
    await session.put("/event.json", {"id": stream.id,
                                      "stream": stream.to_json()})


async def event_stream_move(session: BaseSession,
                            source: Union[EventStream, str, int],
                            destination: Union[Folder, str, int]) -> None:
    data = {}

    if type(source) is EventStream:
        data["src_id"] = source.id
    elif type(source) is int:
        data["src_id"] = source
    elif type(source) is str:
        data["src_path"] = source
    else:
        raise errors.ApiError("Invalid source datatype. Must be EventStream, Path, or ID")

    if type(destination) is Folder:
        data["dest_id"] = destination.id
    elif type(destination) is int:
        data["dest_id"] = destination
    elif type(destination) is str:
        data["dest_path"] = destination
    else:
        raise errors.ApiError("Invalid destination datatype. Must be Folder, Path, or ID")
    await session.put("/event/move.json", data)


async def event_stream_write(session: BaseSession,
                             stream: Union[EventStream, str, int],
                             events: List[Event]) -> List[Event]:
    data = {}
    if type(stream) is EventStream:
        data["id"] = stream.id
    elif type(stream) is int:
        data["id"] = stream
    elif type(stream) is str:
        data["path"] = stream
    else:
        raise errors.ApiError("Invalid stream datatype. Must be EventStream, Path, or ID")
    # post events in blocks
    rx_events = []
    for idx in range(0, len(events), 500):
        chunk = events[idx:idx + 500]
        data['events'] = [e.to_json() for e in events[idx:idx + 500]]
        resp = await session.post("/event/data.json", data)
        rx_events += [event_from_json(e) for e in resp["events"]]
        # copy the ids over
        for i in range(len(chunk)):
            chunk[i].id = rx_events[i].id
    return events


async def event_stream_read(session: BaseSession,
                            stream: Union[EventStream, str, int],
                            start_time: Optional[int] = None,
                            end_time: Optional[int] = None,
                            limit=None,
                            json_filter=None) -> List[Event]:
    params = {}
    if type(stream) is EventStream:
        params["id"] = stream.id
    elif type(stream) is int:
        params["id"] = stream
    elif type(stream) is str:
        params["path"] = stream
    else:
        raise errors.ApiError("Invalid stream datatype. Must be EventStream, Path, or ID")
    if start_time is not None:
        params['start'] = int(start_time)
    if end_time is not None:
        params['end'] = int(end_time)
    if limit is not None:
        if limit <= 0:
            raise errors.ApiError("Limit must be > 0")
        params['limit'] = limit
        params['return-subset'] = 1
    if json_filter is not None:
        params['filter'] = json_filter
    resp = await session.get("/event/data.json", params)
    return [event_from_json(e) for e in resp["events"]]


async def event_stream_remove(session: BaseSession,
                              stream: Union[EventStream, str, int],
                              start_time: Optional[int] = None,
                              end_time: Optional[int] = None,
                              json_filter=None) -> None:
    params = {}
    if type(stream) is EventStream:
        params["id"] = stream.id
    elif type(stream) is int:
        params["id"] = stream
    elif type(stream) is str:
        params["path"] = stream
    else:
        raise errors.ApiError("Invalid stream datatype. Must be EventStream, Path, or ID")
    if start_time is not None:
        params['start'] = int(start_time)
    if end_time is not None:
        params['end'] = int(end_time)
    if json_filter is not None:
        params['filter'] = json_filter
    await session.delete("/event/data.json", params)
