from sqlalchemy.orm import relationship
from sqlalchemy import (Column, Integer, String,
                        Boolean, Enum, ForeignKey)
from typing import List, Dict, TYPE_CHECKING
import configparser
import enum
import json
import re
from operator import attrgetter

from joule.models.meta import Base
from joule.models.errors import ConfigurationError
from joule.models.data_store.data_store import StreamInfo
from joule.models import element

if TYPE_CHECKING:
    from joule.models import (Folder)  # pragma: no cover


class Stream(Base):
    __tablename__ = 'stream'
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
    keep_us: int = Column(Integer, default=KEEP_ALL)

    description: str = Column(String)
    folder_id: int = Column(Integer, ForeignKey('folder.id'))
    folder: "Folder" = relationship("Folder", back_populates="streams")
    elements: List[element.Element] = relationship("Element",
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
        return self.is_configured or self.is_destination or self.is_source

    @property
    def active(self):
        return self.is_source or self.is_destination

    @property
    def layout(self):
        return "%s_%d" % (self.datatype.name.lower(), len(self.elements))

    @property
    def decimated_layout(self):
        # decimations are floats (min,mean,max) tuples
        return "float32_%d" % (len(self.elements) * 3)

    @property
    def data_width(self):
        return len(self.elements) + 1

    def to_json(self, info: Dict[int, StreamInfo] = None):

        if info is not None and self.id in info:
            data_info = info[self.id].to_json()
        else:
            data_info = None

        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'datatype': self.datatype.name,
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


def from_json(data: Dict) -> Stream:
    elements = []
    for item in data["elements"]:
        elements.append(element.from_json(item))
    return Stream(id=data["id"],
                  name=data["name"],
                  description=data["description"],
                  datatype=Stream.DATATYPE[data["datatype"]],
                  keep_us=data["keep_us"],
                  decimate=data["decimate"],
                  is_configured=data["is_configured"],
                  is_source=data["is_source"],
                  is_destination=data["is_destination"],
                  elements=elements)


def from_config(config: configparser.ConfigParser) -> Stream:
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


def validate_name(name: str) -> str:
    if len(name) == 0:
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
