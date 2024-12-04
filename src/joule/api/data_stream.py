from typing import Optional, Dict, List

from .session import BaseSession
from .folder_type import Folder

from joule import errors
from joule.constants import EndPoints

class DataStream:
    """
    API DataStream model. See :ref:`sec-node-data-stream-actions` for details on using the API to
    manipulate data streams. Streams are locked if they are active or statically configured. When
    creating a stream manually, omit the ID and status attributes (**is_configured**, **is_source**, **is_destination**, **active**, and **locked**),
    these are set by the Joule server.

    Parameters:
        name (str): stream name, must be unique in the parent
        description (str): optional field
        datatype (str): element datatype
        keep_us (int): store the last N microseconds of data (-1 to keep all and 0 to keep none)
        is_configured: is the stream statically configured with a `.conf` file
        is_source: is the stream an active data source
        is_destination: is the stream an active data destination
        active (bool): is the stream a source or destination
        locked (bool): is the stream active or configured
        decimate (bool): is the stream data decimated for visualization
        elements (List[Element]): list of the stream elements

    """

    def __init__(self,
                 name: str = "", description: str = "",
                 datatype: str = "float32", keep_us: int = -1,
                 elements: List['Element'] = None):
        self._id = None
        self.name = name
        self.description = description
        self.datatype = datatype
        self.keep_us = keep_us  # -1 = KEEP ALL
        self.is_configured = False
        self.is_source = False
        self.is_destination = False
        self.locked = False
        self.active = False
        self.decimate = True

        if elements is None:
            elements = []
        self.elements = elements

    def __repr__(self):
        return "<joule.api.DataStream id=%r name=%r description=%r datatype=%r is_configured=%r is_source=%r is_destination=%r locked=%r decimate=%r>" % (
            self._id, self.name, self.description,
            self.datatype, self.is_configured,
            self.is_source, self.is_destination,
            self.locked, self.decimate)

    @property
    def id(self) -> int:
        if self._id is None:
            raise errors.ApiError("this is a local model with no ID. See API docs")
        return self._id

    @id.setter
    def id(self, value: int):
        self._id = value

    @property
    def layout(self):
        return self.datatype.lower() + '_' + str(len(self.elements))

    def to_json(self) -> Dict:
        return {
            "id": self._id,
            "name": self.name,
            "description": self.description,
            "is_configured": self.is_configured,
            "is_source": self.is_source,
            "is_destination": self.is_destination,
            "datatype": self.datatype,
            "keep_us": self.keep_us,
            "locked": self.locked,
            "active": self.active,
            "decimate": self.decimate,
            "elements": [e.to_json() for e in self.elements]
        }


def from_json(json) -> DataStream:
    my_stream = DataStream()
    my_stream.id = json['id']
    my_stream.name = json['name']
    my_stream.description = json['description']
    my_stream.datatype = json['datatype']
    my_stream.decimate = json['decimate']
    my_stream.keep_us = json['keep_us']
    my_stream.is_configured = json['is_configured']
    my_stream.is_source = json['is_source']
    my_stream.is_destination = json['is_destination']
    my_stream.locked = json['locked']
    my_stream.active = json['active']
    my_stream.elements = [elem_from_json(item) for item in json['elements']]
    return my_stream


class Element:
    """
    API Element model. Streams have one or more elements. See :ref:`sec-data-streams` for details on the stream data model.

    Parameters:
        id (int): unique numeric ID assigned by Joule
        index (int): column position in the data array (0 = first element)
        name (str): element name
        units (str): unit of measurement, may be any string
        plottable (bool): should the element be visible in the Lumen plotting interface
        display_type [continous|discrete|event]: plot type, defaults to continuous
        offset (float): offset data visualization by ``y=(x-offset)*scale_factor``
        scale_factor (float): scale data visualation with above equation
        default_max (float): fix auto scale max (set to None to fit plotted data)
        default_min (float): fix auto scale min (set to None to fit plotted data)
    """

    def __init__(self, name: str = "", units: str = "",
                 plottable: bool = True,
                 display_type: str = 'continuous'):
        self.id = None
        self.index = None
        self.name = name
        self.units = units
        self.plottable = plottable
        self.display_type = display_type
        self.offset = 0
        self.scale_factor = 1.0
        self.default_max = None
        self.default_min = None

    def __repr__(self):
        return "<joule.api.Element id=%r index=%r, name=%r units=%r plottable=%r display_type=%r>" % (
            self.id, self.index, self.name,
            self.units, self.plottable,
            self.display_type)

    def to_json(self) -> Dict:
        return {
            'id': self.id,
            'index': self.index,
            'name': self.name,
            'units': self.units,
            'plottable': self.plottable,
            'display_type': self.display_type,
            'offset': self.offset,
            'scale_factor': self.scale_factor,
            'default_max': self.default_max,
            'default_min': self.default_min
        }


def elem_from_json(json) -> Element:
    my_elem = Element()
    my_elem.id = json['id']
    my_elem.index = json['index']
    my_elem.name = json['name']
    my_elem.units = json['units']
    my_elem.plottable = json['plottable']
    my_elem.display_type = json['display_type']
    my_elem.offset = json['offset']
    my_elem.scale_factor = json['scale_factor']
    my_elem.default_min = json['default_min']
    my_elem.default_max = json['default_max']
    return my_elem


class DataStreamInfo:
    """
        API DataStreamInfo model. Received from :meth:`Node.data_stream_info` and should not be created directly.

        .. warning::
            Rows and Bytes values are approximate

        Parameters:
            start (int): timestamp in UNIX microseconds of the first data element
            end (int): timestamp in UNIX microsseconds of the last data element
            rows (int): approximate rows of data in the stream
            bytes (int): approximate size of the data on disk
            total_time (int): data duration in microseconds (start-end)

        """

    def __init__(self, start: Optional[int], end: Optional[int], rows: int,
                 total_time: int = 0, bytes: int = 0):
        self.start = start
        self.end = end
        self.rows = rows
        self.bytes = bytes
        self.total_time = total_time

    def __repr__(self):
        return "<joule.api.DataStreamInfo start=%r end=%r rows=%r, total_time=%r>" % (
            self.start, self.end, self.rows, self.total_time)


def info_from_json(json) -> DataStreamInfo:
    if json is not None:

        return DataStreamInfo(json['start'],
                              json['end'],
                              json['rows'],
                              json['total_time'],
                              json['bytes'])
    else:
        return DataStreamInfo(None,
                              None,
                              0,
                              0,
                              0)


async def data_stream_delete(session: BaseSession,
                             stream: DataStream | str |int) -> None:
    data = {}
    if type(stream) is DataStream:
        data["id"] = stream.id
    elif type(stream) is int:
        data["id"] = stream
    elif type(stream) is str:
        data["path"] = stream
    else:
        raise errors.InvalidDataStreamParameter()

    await session.delete(EndPoints.stream, data)


async def data_stream_create(session: BaseSession,
                             stream: DataStream, folder: Folder | str | int) -> DataStream:
    data = {"stream": stream.to_json()}

    if type(folder) is Folder:
        data["dest_id"] = folder.id
    elif type(folder) is int:
        data["dest_id"] = folder
    elif type(folder) is str:
        data["dest_path"] = folder
    else:
        raise errors.ApiError("Invalid folder datatype. Must be Folder, Path, or ID")

    resp = await session.post(EndPoints.stream, json=data)
    return from_json(resp)


async def data_stream_info(session: BaseSession,
                           stream: DataStream | str | int) -> DataStreamInfo:
    data = {}

    if type(stream) is DataStream:
        data["id"] = stream.id
    elif type(stream) is int:
        data["id"] = stream
    elif type(stream) is str:
        data["path"] = stream
    else:
        raise errors.InvalidDataStreamParameter()

    resp = await session.get(EndPoints.stream, data)
    return info_from_json(resp['data_info'])


async def data_stream_get(session: BaseSession,
                          stream: DataStream | str | int) -> DataStream:
    data = {}

    if type(stream) is DataStream:
        data["id"] = stream.id
    elif type(stream) is int:
        data["id"] = stream
    elif type(stream) is str:
        data["path"] = stream
    else:
        raise errors.InvalidDataStreamParameter()
    data["no-info"]=''
    resp = await session.get(EndPoints.stream, data)
    return from_json(resp)


async def data_stream_update(session: BaseSession,
                             stream: DataStream) -> None:
    await session.put(EndPoints.stream, {"id": stream.id,
                                       "stream": stream.to_json()})


async def data_stream_move(session: BaseSession,
                           source: DataStream | str | int,
                           destination: Folder | str | int) -> None:
    data = {}

    if type(source) is DataStream:
        data["src_id"] = source.id
    elif type(source) is int:
        data["src_id"] = source
    elif type(source) is str:
        data["src_path"] = source
    else:
        raise errors.ApiError("Invalid source datatype. Must be DataStream, Path, or ID")

    if type(destination) is Folder:
        data["dest_id"] = destination.id
    elif type(destination) is int:
        data["dest_id"] = destination
    elif type(destination) is str:
        data["dest_path"] = destination
    else:
        raise errors.ApiError("Invalid destination datatype. Must be Folder, Path, or ID")
    await session.put(EndPoints.stream_move, data)


async def data_stream_annotation_delete(session: BaseSession,
                                        stream: DataStream | str | int,
                                        start: Optional[int] = None,
                                        end: Optional[int] = None):
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
        raise errors.ApiError("Invalid source datatype. Must be DataStream, Path, or ID")

    await session.delete(EndPoints.stream_annotations, params=data)
