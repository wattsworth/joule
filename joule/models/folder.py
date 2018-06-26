from sqlalchemy.orm import relationship, backref, Session
from sqlalchemy import Column, Integer, String, ForeignKey
from typing import List, TYPE_CHECKING, Optional
import logging
from joule.models.errors import ConfigurationError
from joule.models.stream import Stream
from joule.models.meta import Base

logger = logging.getLogger('joule')


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

    def find_stream_by_segments(self, segments: List[str]) -> Optional[Stream]:
        if len(segments) == 1:
            for stream in self.streams:
                if stream.name == segments[0]:
                    return stream
            else:
                return None
        for child in self.children:
            if child.name == segments[0]:
                return child.find_stream_by_segments(segments[1:])
        else:
            return None

    def __repr__(self):
        if self.id is None:
            return "<Folder(id=<not assigned>, name='%s')>" % self.name
        else:
            return "<Folder(id=%d, name='%s')>" % (self.id, self.name)

    def to_json(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'children': [c.to_json() for c in self.children],
            'streams': [s.to_json() for s in self.streams]
        }


def root(db: Session) -> Folder:
    root_folder = db.query(Folder). \
        filter_by(parent=None). \
        one_or_none()
    if root_folder is None:
        root_folder = Folder(name="root")
        db.add(root_folder)
        logger.info("creating root folder")
    return root_folder


def find_or_create(path: str, db: Session, parent=None) -> Folder:
    if len(path) == 0 or path[0] != '/':
        raise ConfigurationError("invalid path [%s]" % path)
    if parent is None:
        parent = root(db)
    if path == '/':
        return parent
    path_chunks = list(reversed(path.split('/')[1:]))
    if len(path_chunks) == 0:
        return parent
    name = path_chunks.pop()
    folder: Folder = db.query(Folder).filter_by(parent=parent, name=name). \
        one_or_none()
    if folder is None:
        folder = Folder(name=name)
        parent.children.append(folder)
        db.add(folder)
    sub_path = '/' + '/'.join(reversed(path_chunks))
    return find_or_create(sub_path, db, folder)


def find_stream_by_path(path: str, db: Session) -> Optional[Stream]:
    segments = path[1:].split('/')
    return root(db).find_stream_by_segments(segments)
