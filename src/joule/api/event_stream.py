from typing import Optional, Dict, Union, List
import json
import re

from .session import BaseSession
from .folder_type import Folder
from .event import Event
from .event import from_json as event_from_json
from joule import errors
from joule.utilities.validators import validate_event_fields

class EventStream:
    """
        API EventStream model. See :ref:`sec-node-event-stream-actions` for details on using the API to
        manipulate event streams.

        Parameters:
            name (str): stream name, must be unique in the parent
            description (str): optional field
    """

    def __init__(self, name: str = "",
                 description: str = "",
                 chunk_duration: str = "",
                 chunk_duration_us: Optional[int] = None,
                 keep_us: int = -1,
                 event_fields: Optional[Dict[str, str]] = None):
        self._id = None
        self.name = name
        self.description = description
        if chunk_duration_us is not None:
            if chunk_duration != "":
                raise Exception("specify either chunk_duration or chunk_duration_us, not both")
            self.chunk_duration_us = chunk_duration_us
        else:
            self.chunk_duration_us = self._parse_time_duration(chunk_duration)
        if event_fields is None:
            self.event_fields = {}
        else:
            self.event_fields = validate_event_fields(event_fields)
        self.keep_us = keep_us

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
            "event_fields": self.event_fields,
            "chunk_duration_us": self.chunk_duration_us,
            "keep_us": self.keep_us
        }

    def __repr__(self):
        return "<joule.api.EventStream id=%r name=%r description=%r>" % (
            self._id, self.name, self.description
        )
        

    def _parse_time_duration(self, duration_str):
        # if duration is already a number interpret it as us
        try:
            return int(duration_str)
        except ValueError:
            pass
        # if it is empty use 0 (no hypertables)
        if duration_str == "":
            return 0
        #print(f"duration string: {duration_str}")
        # otherwise expect a time unit and compute accordingly
        match = re.fullmatch(r'^(\d+)([hdwmy])$', duration_str)
        if match is None:
            raise errors.ApiError("invalid duration "
                                  "use format #unit (eg 1w)")

        units = {
            'h': 60 * 60 * 1e6,  # hours
            'd': 24 * 60 * 60 * 1e6,  # days
            'w': 7 * 24 * 60 * 60 * 1e6,  # weeks
            'm': 4 * 7 * 24 * 60 * 60 * 1e6,  # months
            'y': 365 * 24 * 60 * 60 * 1e6  # years
        }
        unit = match.group(2)
        time = int(match.group(1))
        if time <= 0:
            raise errors.ApiError("invalid duration "
                                  "use format #unit (eg 1w), none or all")
        return int(time * units[unit])


def from_json(json: dict) -> EventStream:
    my_stream = EventStream()
    my_stream.id = json['id']
    my_stream.name = json['name']
    my_stream.description = json['description']
    my_stream.event_fields = json['event_fields']
    my_stream.keep_us = json['keep_us']
    # use a default of 0 for backwards compatability
    my_stream.chunk_duration_us = json.get("chunk_duration_us", 0)
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
        return "<joule.api.EventStreamInfo start=%r end=%r event_count=%r, total_time=%r>" % (
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
        data["dest_id"] = folder.id  # raises error if id is None
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
        data["id"] = stream.id  # raises error if id is None
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
                           chunk_duration: str = "",
                           chunk_duration_us: Optional[int] = None,
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
        event_stream = EventStream(name, description,
                                   chunk_duration=chunk_duration,
                                   chunk_duration_us=chunk_duration_us,
                                   event_fields=event_fields)
        return await event_stream_create(session, event_stream, path)
    return from_json(resp)


async def event_stream_update(session: BaseSession,
                              stream: EventStream) -> None:
    # validate the event fields before sending
    validate_event_fields(stream.event_fields)
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


async def event_stream_count(session: BaseSession,
                             stream: Union[EventStream, str, int],
                             start_time: Optional[int],
                             end_time: Optional[int],
                             json_filter,
                             include_on_going_events) -> List[Event]:
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
    if include_on_going_events:
        params['include-on-going-events'] = 1
    resp = await session.get("/event/data/count.json", params)
    return resp["count"]


async def event_stream_read(session: BaseSession,
                            stream: Union[EventStream, str, int],
                            start_time: Optional[int],
                            end_time: Optional[int],
                            limit,
                            json_filter,
                            include_on_going_events) -> List[Event]:
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
    # enforce a limit, do not allow arbitrarily large reads
    limit = int(limit)
    if limit <= 0:
        raise errors.ApiError("Limit must be > 0")
    params['limit'] = limit + 1  # pad by 1 to check for read overflow, see error message below
    params['return-subset'] = 1
    if json_filter is not None:
        params['filter'] = json_filter
    if include_on_going_events:
        params['include-on-going-events'] = 1
    resp = await session.get("/event/data.json", params)
    events = [event_from_json(e) for e in resp["events"]]
    if len(events) > limit:
        print(f"WARNING: Only returning the first {limit} events in this stream, increase "
              "the limit parameter to retrieve more data or use different "
              "time bounds and/or filter parameters to reduce the number of events returned")
        return events[:-1]
    return events


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
