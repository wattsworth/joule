from sqlalchemy.orm import relationship
from sqlalchemy import Column, Integer, Enum, Float, String, Boolean, ForeignKey
import enum
from typing import Optional, TYPE_CHECKING

from joule.models.meta import Base

if TYPE_CHECKING:
    from joule.models.folder import Stream


class Element(Base):
    __tablename__ = 'element'
    id: int = Column(Integer, primary_key=True)
    name: str = Column(String)
    units: str = Column(String)
    plottable: bool = Column(Boolean)

    class TYPE(enum.Enum):
        DISCRETE = enum.auto()
        CONTINUOUS = enum.auto()
        EVENT = enum.auto()
    type: TYPE = Column(Enum(TYPE), default=2)

    offset: float = Column(Float, default=0, nullable=False)
    scale_factor: float = Column(Float, default=1.0, nullable=False)
    default_max: Optional[float] = Column(Float, default=None)
    default_min: Optional[float] = Column(Float, default=None)
    stream_id: int = Column(Integer, ForeignKey('stream.id'))
    stream: 'Stream' = relationship("Stream", back_populates="elements")

    def __repr__(self):
        return "<Element('%s', '%s')>" % (self.name, self.units)

    def to_json(self):
        return {
            'name': self.name,
            'units': self.units,
            'plottable': self.plottable,
            'type': self.type,
            'offset': self.offset,
            'scale_factor': self.scale_factor,
            'default_max': self.default_max,
            'default_min': self.default_min
        }
