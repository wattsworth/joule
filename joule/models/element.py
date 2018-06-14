from sqlalchemy.orm import relationship
from sqlalchemy import Column, Integer, Enum, Float, String, Boolean, ForeignKey
import configparser
import enum
from typing import Optional, TYPE_CHECKING

from joule.models.meta import Base
from joule.models.errors import ConfigurationError

if TYPE_CHECKING:
    from joule.models.folder import Stream


class Element(Base):
    __tablename__ = 'element'
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
    stream_id: int = Column(Integer, ForeignKey('stream.id'))
    stream: 'Stream' = relationship("Stream", back_populates="elements")

    def __repr__(self):
        return "<Element(name='%s', units='%s', display_type=%s)>" % (self.name, self.units, self.display_type)

    def to_json(self):
        return {
            'name': self.name,
            'units': self.units,
            'plottable': self.plottable,
            'display_type': self.display_type.name,
            'offset': self.offset,
            'scale_factor': self.scale_factor,
            'default_max': self.default_max,
            'default_min': self.default_min
        }


def from_config(config: configparser.ConfigParser):
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
