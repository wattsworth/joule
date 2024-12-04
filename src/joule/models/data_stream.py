from sqlalchemy.orm import relationship, Mapped
from sqlalchemy import (Column, Integer, String,
                        Boolean, Enum, ForeignKey, DateTime)
from sqlalchemy.dialects.postgresql import BIGINT
from typing import List, Dict, Optional, TYPE_CHECKING
import configparser
import enum
import re
from operator import attrgetter
from datetime import datetime, timezone

from joule.models.meta import Base
from joule.errors import ConfigurationError
from joule.models.data_store.data_store import StreamInfo
from joule.models import element, annotation
from joule.utilities import parse_time_interval
if TYPE_CHECKING:
    from joule.models import (Folder)  


class DataStream(Base):
    """
    Attributes:
        name (str): stream name
        description (str): stream description
        datatype (DataStream.DATATYPE): data representation on disk see :ref:`sec-data-streams`
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
    folder: Mapped["Folder"] = relationship("Folder", back_populates="data_streams")
    elements: Mapped[List[element.Element]] = relationship("Element",
                                                           cascade="all, delete-orphan",
                                                           back_populates="stream")
    annotations: Mapped[List[annotation.Annotation]] = relationship("Annotation",
                                                                    cascade="all, delete-orphan",
                                                                    back_populates="stream")
    updated_at: datetime = Column(DateTime(timezone=True), nullable=False)

    def merge_configs(self, other: 'DataStream') -> bool:
        # first update the elements, first make sure
        # both streams have the same number of elements
        # and that they are in the same order
        if len(self.elements) != len(other.elements):
            raise ConfigurationError("incorrect number of elements")
        my_elements = sorted(self.elements, key=attrgetter('index'))
        other_elements = sorted(other.elements, key=attrgetter('index'))
        updated_config = False
        for i in range(len(my_elements)):
            updated_config |= my_elements[i].merge_configs(other_elements[i])

        if (
                self.keep_us != other.keep_us or
                self.decimate != other.decimate or
                self.description != other.description or
                self.is_configured != other.is_configured or
                self.is_destination != other.is_destination or
                self.is_source != other.is_source
        ):
            updated_config = True
        # replace configurable attributes with other's values
        self.keep_us = other.keep_us
        self.decimate = other.decimate
        self.description = other.description
        self.is_configured = other.is_configured
        self.is_destination = other.is_destination
        self.is_source = other.is_source

        if updated_config:
            self.updated_at = datetime.now(timezone.utc)
            return True
        else:
            return False

    def update_attributes(self, attrs: Dict) -> None:
        updated = False
        if 'name' in attrs:
            self.name = validate_name(attrs['name'])
            updated = True
        if 'description' in attrs:
            self.description = attrs['description']
            updated = True
        if 'keep_us' in attrs:
            self.keep_us = attrs['keep_us']
            updated = True
        if 'decimate' in attrs:
            self.decimate = attrs['decimate']
            updated = True
        if 'elements' in attrs:
            element_configs = attrs['elements']
            # make sure the number of configs is correct
            if len(element_configs) != len(self.elements):
                raise ConfigurationError("incorrect number of elements")
            for e in self.elements:
                e.update_attributes(element_configs[e.index])
            updated = True
        if updated:
            self.touch()
    def __str__(self):
        return "DataStream [{name}]".format(name=self.name)

    def __repr__(self):
        return "<DataStream(id=%r, name='%s', datatype=%r)>" % (
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

    # update timestamps on all folders in hierarchy
    def touch(self, now: Optional[datetime] = None) -> None:
        if now is None:
            now = datetime.now(timezone.utc)
        self.updated_at = now
        if self.folder is not None:
            self.folder.touch(now)

    def to_json(self, info: Dict[int, StreamInfo] = None) -> Dict:
        """
          Args:
            info: optional content added to ``data_info`` field

        Returns: Dictionary of DataStream attributes

        """



        resp = {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'datatype': self.datatype.name.lower(),
            'layout': self.layout,
            'keep_us': self.keep_us,
            'is_configured': self.is_configured,
            'is_source': self.is_source,
            'is_destination': self.is_destination,
            'updated_at': self.updated_at.isoformat(),
            'locked': self.locked,  # meta attribute
            'active': self.active,  # meta attribute
            'decimate': self.decimate,
            'elements': [e.to_json() for e in sorted(self.elements, key=attrgetter('index'))],
        }
        if info is not None and self.id in info:
            resp['data_info'] = info[self.id].to_json()
        return resp


def from_json(data: Dict) -> DataStream:
    """
    Construct a DataStream from a dictionary of attributes produced by
    :meth:`DataStream.to_json`

    Args:
        data: attribute dictionary

    Returns: DataStream

    """
    elements = []
    index = 0
    for item in data["elements"]:
        item["index"] = index
        elements.append(element.from_json(item))
        index += 1

    return DataStream(id=data["id"],
                      name=validate_name(data["name"]),
                      description=data["description"],
                      datatype=validate_datatype(data["datatype"].upper()),
                      keep_us=data["keep_us"],
                      decimate=data["decimate"],
                      is_configured=data["is_configured"],
                      is_source=data["is_source"],
                      is_destination=data["is_destination"],
                      elements=elements,
                      updated_at=datetime.now(timezone.utc))



def from_config(config: configparser.ConfigParser) -> DataStream:
    """
    Construct a DataStream from a configuration file

    Args:
        config: parsed *.conf file

    Returns: DataStream

    Raises: ConfigurationError

    Example Config:

        [Main]
        #required settings
        name = stream name
        path = /stream/path
        datatype = float32
        keep = 1w

        #optional settings (defaults)
        decimate = yes

        [Element1]
        #required settings
        name = element name

        #optional settings (defaults)
        plottable = yes
        display_type = continuous
        offset = 0.0
        scale_factor = 1.0
        default_max = None
        default_min = None

        #additional elements...
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
        stream = DataStream(name=name, description=description,
                            datatype=datatype, keep_us=keep_us, decimate=decimate,
                            updated_at=datetime.now(timezone.utc))
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
    if name is None or len(name) == 0:
        raise ConfigurationError("missing name")
    if '/' in name:
        raise ConfigurationError("invalid name, '\\' not allowed")
    return name


def validate_datatype(datatype: str) -> DataStream.DATATYPE:
    try:
        return DataStream.DATATYPE[datatype.upper()]
    except KeyError as e:
        valid_types = ", ".join([m.name.lower() for m in DataStream.DATATYPE])
        raise ConfigurationError("invalid datatype [%s], choose from [%s]" %
                                 (datatype, valid_types)) from e


def validate_keep(keep: str) -> int:
    try:
        return parse_time_interval(keep)
    except ValueError as e:
        raise ConfigurationError("Invalid Data Stream [keep] value: %s" % (e)) from e
    
