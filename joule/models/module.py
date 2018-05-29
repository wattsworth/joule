from sqlalchemy.orm import relationship
from sqlalchemy import (Column, String, Integer,
                        Boolean, Enum)
import enum
from typing import List, TYPE_CHECKING
import configparser

from joule.models.meta import Base
from joule.models.errors import ConfigurationError

if TYPE_CHECKING:
    from joule.models import (Pipe, LogEntry, Argument)

"""
Configuration File:
[Main]
name = module name
description = module description
exec_cmd = /path/to/file
has_interface = no

[Arguments]
key = value

[Inputs]
#name = full_path:layout
labjack = /labjack/device3/data:float32_6
path2 = /nilmdb/input/stream2:int8_2
  ....
pathN = /nilmdb/input/streamN:int8_3

[Outputs]
#name = full_path:layout
path1 = /nilmdb/output/stream1:float32_8
path2 = /nilmdb/output/stream2:float64_2
  ....
pathN = /nilmdb/output/streamN:uint16_10
"""


class Module(Base):
    __tablename__ = 'module'
    id: int = Column(Integer, primary_key=True)
    name: str = Column(String, nullable=False, unique=True)
    exec_cmd: str = Column(String, nullable=False)
    description: str = Column(String, default="")
    locked: bool = Column(Boolean, default=False)

    class STATUS(enum.Enum):
        LOADED = enum.auto()
        RUNNING = enum.auto()
        FAILED = enum.auto()
        UNKNOWN = enum.auto()

    status: STATUS = Column(Enum(STATUS), default=STATUS.UNKNOWN)
    has_interface: bool = Column(Boolean, default=False)
    interface_socket: str = Column(String, default="")
    pipes: List['Pipe'] = relationship("Pipe",
                                       cascade="all, delete-orphan",
                                       back_populates="module")
    arguments: List['Argument'] = relationship("Argument",
                                               cascade="all, delete-orphan",
                                               back_populates="module")
    log_entries: List['LogEntry'] = relationship("LogEntry",
                                                 cascade="all, delete-orphan",
                                                 back_populates="module")

    def __repr__(self):
        return "<Module(id=%r, name=%s)>" % (self.id, self.name)


def from_config(config: configparser.ConfigParser) -> Module:
    try:
        main_configs = config["Main"]
    except KeyError as e:
        raise ConfigurationError("Missing section [%s]" % e.args[0]) from e
    return Module(name=main_configs["name"], description=main_configs["description"])