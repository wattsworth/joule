from sqlalchemy.orm import relationship
from sqlalchemy import (Column, Integer, String,
                        Boolean, Enum, ForeignKey)
from sqlalchemy.dialects.postgresql import BIGINT
from typing import List, Dict, TYPE_CHECKING
import configparser
import enum
import re
from operator import attrgetter

from joule.models.meta import Base
from joule.errors import ConfigurationError
from joule.models.data_store.data_store import StreamInfo
from joule.models import element, annotation

if TYPE_CHECKING:
    from joule.models import (Folder)  # pragma: no cover


class Stream(Base):
    """
    Attributes:
        name (str): stream name
        description (str): stream description
        datatype (Stream.DATATYPE): data representation on disk see :ref:`sec-streams`
        decimate (bool): whether to store decimated data for stream visualization
        folder (joule.Folder): parent Folder
        elements (List[joule.Element]): array of stream elements
        keep_us (int): microseconds of data to keep (KEEP_NONE=0, KEEP_ALL=-1).

    """
    __tablename__ = 'stream'
    __table_args__ = {"schema": "metadata"}

    id: int = Column(Integer, primary_key=True)
    name: str = Column(String, nullable=False)

    class DATATYPE(enum.Enum):
        FLOAT64 = enum.auto()
        FLOAT32 = enum.auto()
        INT64 = enum.auto()
        INT32 = enum.auto()
        INT16 = enum.auto()
        INT8 = enum.auto()
        UINT64 = enum.auto()
        UINT32 = enum.auto()
        UINT16 = enum.auto()
        UINT8 = enum.auto()

    datatype: DATATYPE = Column(Enum(DATATYPE), nullable=False)
    decimate: bool = Column(Boolean, default=True)

    # do not allow property changes if any of the following are true
    is_source: bool = Column(Boolean, default=False)
    is_destination: bool = Column(Boolean, default=False)
    is_configured: bool = Column(Boolean, default=False)

    KEEP_ALL = -1
    KEEP_NONE = 0
    keep_us: int = Column(BIGINT, default=KEEP_ALL)

    description: str = Column(String)
    folder_id: int = Column(Integer, ForeignKey('metadata.folder.id'))
    folder: "Folder" = relationship("Folder", back_populates="streams")
    elements: List[element.Element] = relationship("Element",
                                                   cascade="all, delete-orphan",
                                                   back_populates="stream")
    annotations: List[annotation.Annotation] = relationship("Annotation",
                                                            cascade="all, delete-orphan",
                                                            back_populates="stream")

    def merge_configs(self, other: 'Stream') -> None:
        # replace configurable attributes with other's values
        self.keep_us = other.keep_us
        self.decimate = other.decimate
        self.description = other.description
        self.is_configured = other.is_configured
        self.is_destination = other.is_destination
        self.is_source = other.is_source
        self.elements = other.elements

    def update_attributes(self, attrs: Dict) -> None:
        if 'name' in attrs:
            self.name = validate_name(attrs['name'])
        if 'description' in attrs:
            self.description = attrs['description']
        if 'elements' in attrs:
            element_configs = attrs['elements']
            # make sure the number of configs is correct
            if len(element_configs) != len(self.elements):
                raise ConfigurationError("incorrect number of elements")
            for e in self.elements:
                e.update_attributes(element_configs[e.index])

    def __str__(self):
        return "Stream [{name}]".format(name=self.name)

    def __repr__(self):
        return "<Stream(id=%r, name='%s', datatype=%r)>" % (
            self.id, self.name, self.datatype)

    @property
    def locked(self):
        """
        bool: true if the stream has a configuration file or is an active
         part of the data pipeline. Attributes of locked streams cannot be changed.
        """
        return self.is_configured or self.is_destination or self.is_source

    @property
    def active(self):
        """
        bool: true if the stream is part of the data pipeline
        """
        return self.is_source or self.is_destination

    @property
    def layout(self):
        """
        str: formatted string specifying the datatype and number of elements
        """
        return "%s_%d" % (self.datatype.name.lower(), len(self.elements))

    @property
    def decimated_layout(self):
        # decimations are floats (min,mean,max) tuples
        return "float32_%d" % (len(self.elements) * 3)

    @property
    def data_width(self) -> int:
        return len(self.elements) + 1

    @property
    def is_remote(self) -> bool:
        """
        bool: true if the stream resides on a remote system
        """
        try:
            return self._remote_node is not None
        except AttributeError:
            return False

    @property
    def remote_node(self) -> str:
        """
        str: URL of remote host, blank if the stream is local
        """
        try:
            return self._remote_node
        except AttributeError:
            return ''

    @property
    def remote_path(self) -> str:
        """
        str: path on remote host, blank if the stream is local
        """
        try:
            return self._remote_path
        except AttributeError:
            return ''

    def set_remote(self, node: str, path: str):
        """
        Associate the stream with a remote system
        Args:
            url: remote URL
            path: stream path on remote system
        """
        self._remote_node = node
        self._remote_path = path

    def to_json(self, info: Dict[int, StreamInfo] = None) -> Dict:
        """
          Args:
            info: optional content added to ``data_info`` field

        Returns: Dictionary of Stream attributes

        """

        if info is not None and self.id in info:
            data_info = info[self.id].to_json()
        else:
            data_info = None

        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'datatype': self.datatype.name.lower(),
            'layout': self.layout,
            'keep_us': self.keep_us,
            'is_configured': self.is_configured,
            'is_source': self.is_source,
            'is_destination': self.is_destination,
            'locked': self.locked,  # meta attribute
            'active': self.active,  # meta attribute
            'decimate': self.decimate,
            'elements': [e.to_json() for e in sorted(self.elements, key=attrgetter('index'))],
            'data_info': data_info
        }

    def to_nilmdb_metadata(self) -> Dict:
        return {
            'name': self.name,
            'name_abbrev': '',
            'delete_locked': False,
            'streams': [e.to_nilmdb_metadata() for e in self.elements]
        }


def from_json(data: Dict) -> Stream:
    """
    Construct a Stream from a dictionary of attributes produced by
    :meth:`Stream.to_json`

    Args:
        data: attribute dictionary

    Returns: Stream

    """
    elements = []
    index = 0
    for item in data["elements"]:
        item["index"] = index
        elements.append(element.from_json(item))
        index += 1

    return Stream(id=data["id"],
                  name=validate_name(data["name"]),
                  description=data["description"],
                  datatype=validate_datatype(data["datatype"].upper()),
                  keep_us=data["keep_us"],
                  decimate=data["decimate"],
                  is_configured=data["is_configured"],
                  is_source=data["is_source"],
                  is_destination=data["is_destination"],
                  elements=elements)


def from_config(config: configparser.ConfigParser) -> Stream:
    """
    Construct a Stream from a configuration file

    Args:
        config: parsed *.conf file

    Returns: Stream

    Raises: ConfigurationError

    """
    try:
        main_configs: configparser.ConfigParser = config["Main"]
    except KeyError as e:
        raise ConfigurationError("Missing section [%s]" % e) from e
    try:
        datatype = validate_datatype(main_configs["datatype"])
        keep_us = validate_keep(main_configs.get("keep", fallback="all"))
        decimate = main_configs.getboolean("decimate", fallback=True)
        name = validate_name(main_configs["name"])
        description = main_configs.get("description", fallback="")
        stream = Stream(name=name, description=description,
                        datatype=datatype, keep_us=keep_us, decimate=decimate)
    except KeyError as e:
        raise ConfigurationError("[Main] missing %s" % e.args[0]) from e
    # now try to load the elements
    element_configs = filter(lambda sec: re.match(r"Element\d", sec),
                             config.sections())
    index = 0
    for name in element_configs:
        try:
            e = element.from_config(config[name])
            e.index = index
            index += 1
            stream.elements.append(e)
        except ConfigurationError as e:
            raise ConfigurationError("element <%s> %s" % (name, e)) from e
    # make sure we have at least one element
    if len(stream.elements) == 0:
        raise ConfigurationError(
            "missing element configurations, must have at least one")
    return stream


def from_nilmdb_metadata(config_data: Dict, layout: str) -> Stream:
    datatype = validate_datatype(layout.split('_')[0])
    nelem = int(layout.split('_')[1])
    if 'streams' in config_data:
        elements = config_data['streams']
    else:
        elements = [{'column': i, 'name': "Element%d" % (i+1), 'units': None,
                     'scale_factor': 1.0, 'offset': 0.0, 'plottable': True,
                     'discrete': False, 'default_min': None, 'default_max': None} for
                    i in range(nelem)]
    stream = Stream(name=config_data['name'], description='', datatype=datatype,
                    keep_us=Stream.KEEP_ALL, decimate=True)
    for metadata in elements:
        elem = element.from_nilmdb_metadata(metadata)
        stream.elements.append(elem)
    return stream


def validate_name(name: str) -> str:
    if name is None or len(name) == 0:
        raise ConfigurationError("missing name")
    if '/' in name:
        raise ConfigurationError("invalid name, '\\' not allowed")
    return name


def validate_datatype(datatype: str) -> Stream.DATATYPE:
    try:
        return Stream.DATATYPE[datatype.upper()]
    except KeyError as e:
        valid_types = ", ".join([m.name.lower() for m in Stream.DATATYPE])
        raise ConfigurationError("invalid datatype [%s], choose from [%s]" %
                                 (datatype, valid_types)) from e


def validate_keep(keep: str) -> int:
    if keep.lower() == "none":
        return Stream.KEEP_NONE
    if keep.lower() == "all":
        return Stream.KEEP_ALL
    match = re.fullmatch(r'^(\d+)([hdwmy])$', keep)
    if match is None:
        raise ConfigurationError("invalid [Stream] keep"
                                 "use format #unit (eg 1w), none or all")

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
        raise ConfigurationError("invalid [Stream] keep"
                                 "use format #unit (eg 1w), none or all")
    return int(time * units[unit])
