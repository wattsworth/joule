from sqlalchemy.orm import relationship
from sqlalchemy import (Column, Integer, String,
                        Boolean, Enum, ForeignKey)
from typing import List, TYPE_CHECKING
import enum

from joule.models.element import Element
from joule.models.meta import Base

if TYPE_CHECKING:
    from joule.models.folder import Folder


class Stream(Base):
    __tablename__ = 'stream'
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

    KEEP_ALL = -1
    KEEP_NONE = 0
    keep_us: int = Column(Integer, default=KEEP_ALL)

    description: str = Column(String)
    id: int = Column(Integer, primary_key=True)
    folder_id: int = Column(Integer, ForeignKey('folder.id'))
    folder: "Folder" = relationship("Folder", back_populates="streams")
    elements: List[Element] = relationship("Element", back_populates="stream")

    def __repr__(self):
        return "<Stream('%s','%s','%s',%r)>" % (self.name,
                                                self.description,
                                                self.datatype,
                                                self.decimate)

    def to_json(self):
        return {
            'name': self.name,
            'description': self.description,
            'datatype': self.datatype,
            'keep_us': self.keep_us,
            'decimate': self.decimate,
            'elements': [e.to_json() for e in self.elements]
        }
