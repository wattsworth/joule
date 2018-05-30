from sqlalchemy.orm import relationship
from sqlalchemy import (Column, Enum, Integer, String, ForeignKey)
import enum
from typing import TYPE_CHECKING

from joule.models.meta import Base

if TYPE_CHECKING:
    from joule.models import (Module, Stream)

print("I'm imported!!!!!!!!!!!")

class Pipe(Base):
    __tablename__ = 'pipe'
    id: int = Column(Integer, primary_key=True)

    class DIRECTION(enum.Enum):
        INPUT = enum.auto()
        OUTPUT = enum.auto()

    name: str = Column(String)
    direction: DIRECTION = Column(Enum(DIRECTION))
    module_id: int = Column(Integer, ForeignKey('module.id'))
    module: 'Module' = relationship("Module", back_populates="pipes")
    stream_id: int = Column(Integer, ForeignKey('stream.id'))
    stream: 'Stream' = relationship("Stream", back_populates="pipes")

    def __repr__(self):
        msg = "<Pipe(name='%s', direction=" % self.name
        if self.direction == Pipe.DIRECTION.INPUT:
            msg += 'INPUT'
        else:
            msg += 'OUTPUT'
        msg += ", module="
        if self.module is not None:
            msg += self.module.name
        else:
            msg += "[None]"
        msg += ", stream="
        if self.stream is not None:
            msg += self.stream.name
        else:
            msg += "[None]"
        msg +='>'
        return msg
