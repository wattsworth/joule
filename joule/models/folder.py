from sqlalchemy.orm import relationship, backref
from sqlalchemy import Column, Integer, String, ForeignKey
from typing import List, TYPE_CHECKING

from joule.models.stream import Stream
from joule.models.meta import Base


class Folder(Base):
    __tablename__ = 'folder'
    name: str = Column(String, nullable=False)
    description: str = Column(String, nullable=True)
    id: int = Column(Integer, primary_key=True)
    children: List["Folder"] = relationship("Folder",
                                            backref=backref('parent',
                                                            remote_side=[id]))
    streams: List[Stream] = relationship("Stream", back_populates="folder")
    parent_id: int = Column(Integer, ForeignKey('folder.id'))
    if TYPE_CHECKING:
        parent: 'Folder'

    def __repr__(self):
        if self.id is None:
            return "<Folder(id=<not assigned>, name='%s')>" % self.name
        else:
            return "<Folder(id=%d, name='%s')>" % (self.id, self.name)

    def to_json(self):
        return {
            'name': self.name,
            'description': self.description,
            'children': [c.to_json() for c in self.children],
            'streams': [s.to_json() for s in self.streams]
        }
