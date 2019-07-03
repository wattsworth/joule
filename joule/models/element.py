from sqlalchemy.orm import relationship
from sqlalchemy import Column, Integer, Enum, Float, String, Boolean, ForeignKey
import configparser
import enum
from typing import Optional, Dict, TYPE_CHECKING

from joule.models.meta import Base
from joule.errors import ConfigurationError

if TYPE_CHECKING:  # pragma: no cover
    from joule.models.folder import Stream


class Element(Base):
    """
    Attributes:
        name (str): element name
        index (int): order of element in the stream
        units (str): data unit (eg Watts, Volts, etc)
        plottable (bool): whether the data can be visualized as a time series
        offset (float): linear scaling y=mx+b, only applied to Lumen visualizations
        scale_factor (float): linear scaling only applied to Lumen visualizations
        default_min (float): fix lower limit on autoscaling in Lumen visualizations
        default_max (float): fix upper limit on autoscaling in Lumen visualizations
        display_type (Element.DISPLAYTYPE): visualization type
    """
    __tablename__ = 'element'
    __table_args__ = {"schema": "metadata"}

    id: int = Column(Integer, primary_key=True)
    index: int = Column(Integer, nullable=False)
    name: str = Column(String)
    units: str = Column(String)
    plottable: bool = Column(Boolean)

    class DISPLAYTYPE(enum.Enum):
        DISCRETE = enum.auto()
        CONTINUOUS = enum.auto()
        EVENT = enum.auto()

    display_type: DISPLAYTYPE = Column(Enum(DISPLAYTYPE),
                                       default=DISPLAYTYPE.CONTINUOUS)

    offset: float = Column(Float, default=0, nullable=False)
    scale_factor: float = Column(Float, default=1.0, nullable=False)
    default_max: Optional[float] = Column(Float, default=None)
    default_min: Optional[float] = Column(Float, default=None)
    stream_id: int = Column(Integer, ForeignKey('metadata.stream.id'))
    stream: 'Stream' = relationship("Stream", back_populates="elements")

    def __repr__(self):
        return "<Element(name='%s', units='%s', display_type=%s)>" % (self.name, self.units, self.display_type)

    def to_json(self):
        """

        Returns: Dictionary of Element attributes

        """
        if self.display_type is None:
            # make up a default value
            self.display_type = Element.DISPLAYTYPE.CONTINUOUS
        return {
            'id': self.id,
            'index': self.index,
            'name': self.name,
            'units': self.units,
            'plottable': self.plottable,
            'display_type': self.display_type.name,
            'offset': self.offset,
            'scale_factor': self.scale_factor,
            'default_max': self.default_max,
            'default_min': self.default_min
        }

    def to_nilmdb_metadata(self):
        return {
            'column': self.index,
            'name': self.name,
            'units': self.units,
            'scale_factor': self.scale_factor,
            'offset': self.offset,
            'plottable': True,  #TODO: check why elements have NULL fields here?
            'discrete': False,
            'default_min': self.default_min,
            'default_max': self.default_max
        }

    def update_attributes(self, attrs: Dict):
        if 'name' in attrs:
            self.name = validate_name(attrs['name'])
        if 'units' in attrs:
            self.units = attrs['units']
        try:
            if 'plottable' in attrs:
                self.plottable = bool(attrs['plottable'])
            if 'offset' in attrs:
                self.offset = float(attrs['offset'])
            if 'scale_factor' in attrs:
                self.scale_factor = float(attrs['scale_factor'])
            if 'display_type' in attrs:
                self.display_type = validate_type(attrs['display_type'])
            if 'default_max' in attrs:
                x = attrs['default_max']
                if x is not None:
                    x = float(x)
                self.default_max = x
            if 'default_min' in attrs:
                x = attrs['default_min']
                if x is not None:
                    x = float(x)
                self.default_min = x
        except ValueError as e:
            raise ConfigurationError("Invalid element configuration: %r" % e)
        if self.default_max is not None and self.default_min is not None:
            if self.default_max <= self.default_min:
                raise ConfigurationError("[default_min] must be > [default_max]")


def from_json(data: Dict) -> Element:
    return Element(id=data["id"],
                   index=data["index"],
                   name=validate_name(data["name"]),
                   units=data["units"],
                   plottable=data["plottable"],
                   display_type=validate_type(data["display_type"].upper()),
                   offset=data["offset"],
                   scale_factor=data["scale_factor"],
                   default_max=data["default_max"],
                   default_min=data["default_min"])


def from_config(config: configparser.ConfigParser) -> Element:
    name = validate_name(config["name"])
    display_type = validate_type(config.get("display_type", fallback="continuous"))
    units = config.get("units", fallback=None)
    plottable = _get_bool("plottable", config, True)
    offset = _get_float("offset", config, 0.0)
    scale_factor = _get_float("scale_factor", config, 1.0)
    default_max = _get_float("default_max", config, None)
    default_min = _get_float("default_min", config, None)
    # make sure min<=max if set
    if ((default_max is not None and default_min is not None) and
            (default_min >= default_max)):
        raise ConfigurationError("set default_min<default_max or omit for autoscale")
    return Element(name=name, units=units, plottable=plottable,
                   display_type=display_type, offset=offset,
                   scale_factor=scale_factor,
                   default_max=default_max,
                   default_min=default_min)


def from_nilmdb_metadata(config: Dict) -> Element:
    return Element(name=config['name'],
                   display_type=Element.DISPLAYTYPE.CONTINUOUS,
                   units=config['units'],
                   plottable=config['plottable'],
                   offset=config['offset'],
                   scale_factor=config['scale_factor'],
                   default_max=config['default_max'],
                   default_min=config['default_min'],
                   index=config['column'])


def validate_name(name: str) -> str:
    if name == "":
        raise ConfigurationError("missing name")
    return name


def validate_type(display_type: str) -> Element.DISPLAYTYPE:
    try:
        return Element.DISPLAYTYPE[display_type.upper()]
    except KeyError as e:
        valid_types = ", ".join([m.name.lower() for m in Element.DISPLAYTYPE])
        raise ConfigurationError("invalid display_type [%s], choose from [%s]" %
                                 (display_type, valid_types)) from e


def _get_bool(setting: str, config: configparser.ConfigParser, default: bool):
    try:
        return config.getboolean(setting, default)
    except ValueError as e:
        raise ConfigurationError("[%s] invalid value, use True/False" % setting) from e


def _get_float(setting: str, config: configparser.ConfigParser, default):
    try:
        if config[setting] == "None":
            return default
        return config.getfloat(setting, default)
    except KeyError:
        return default
    except ValueError as e:
        raise ConfigurationError("[%s] invalid value, must be a number" %
                                 setting) from e
