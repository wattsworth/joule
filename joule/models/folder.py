from sqlalchemy.orm import relationship, backref, Session
from sqlalchemy import Column, Integer, String, ForeignKey
from typing import List, TYPE_CHECKING, Optional, Dict
import logging
from joule.errors import ConfigurationError
from joule.models.stream import Stream
from joule.models.data_store.data_store import StreamInfo
from joule.models.meta import Base

logger = logging.getLogger('joule')


class Folder(Base):
    __tablename__ = 'folder'
    __table_args__ = {"schema": "metadata"}

    name: str = Column(String, nullable=False)
    description: str = Column(String, nullable=True)
    id: int = Column(Integer, primary_key=True)
    children: List["Folder"] = relationship("Folder",
                                            backref=backref('parent',
                                                            remote_side=[id]))
    streams: List[Stream] = relationship("Stream", back_populates="folder")
    parent_id: int = Column(Integer, ForeignKey('metadata.folder.id'))
    if TYPE_CHECKING:  # pragma: no cover
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

    def update_attributes(self, attrs: Dict) -> None:
        if 'name' in attrs:
            self.name = validate_name(attrs['name'])
        if 'description' in attrs:
            self.description = attrs['description']

    def contains_streams(self) -> bool:
        """does this folder or any of its children have streams?"""
        if len(self.streams) > 0:
            return True
        for c in self.children:
            if c.contains_streams():
                return True
        return False

    @property
    def locked(self):
        """is this the root folder or does this folder or any of its children have locked streams?"""
        if self.parent is None:
            return True
        for f in self.children:
            if f.locked:
                return True
        for s in self.streams:
            if s.locked:
                return True
        return False

    def __repr__(self):
        if self.id is None:
            return "<Folder(id=<not assigned>, name='%s')>" % self.name
        else:
            return "<Folder(id=%d, name='%s')>" % (self.id, self.name)

    def to_json(self, info: Dict[int, StreamInfo] = None):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'locked': self.locked,
            'children': [c.to_json(info) for c in self.children],
            'streams': [s.to_json(info) for s in self.streams]
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


def find(path: str, db: Session, create=False, parent=None) -> Optional[Folder]:
    if len(path) == 0 or path[0] != '/':
        raise ConfigurationError("invalid path [%s]" % path)
    if parent is None:
        parent = root(db)
    if path == '/':
        return parent
    path_chunks = list(reversed(path.split('/')[1:]))
    # if len(path_chunks) == 0: # never used
    #    return parent
    name = path_chunks.pop()
    folder: Folder = db.query(Folder).filter_by(parent=parent, name=name). \
        one_or_none()
    if folder is None:
        if not create:
            return None
        folder = Folder(name=name)
        parent.children.append(folder)
        db.add(folder)
    sub_path = '/' + '/'.join(reversed(path_chunks))
    return find(sub_path, db, create=create, parent=folder)


def find_stream_by_path(path: str, db: Session) -> Optional[Stream]:
    segments = path[1:].split('/')
    return root(db).find_stream_by_segments(segments)


# return the file path
def get_stream_path(stream: Stream) -> Optional[str]:
    if stream.is_remote:
        return "[%s] %s" % (stream.remote_node, stream.remote_path)
    if stream.folder is None:
        return None

    def _get_path(folder: Folder, path: str):
        if folder.parent is None:
            return "/"+path
        return _get_path(folder.parent, folder.name+"/"+path)

    return _get_path(stream.folder, stream.name)


def validate_name(name: str) -> str:
    if name is None or len(name) == 0:
        raise ConfigurationError("missing name")
    if '/' in name:
        raise ConfigurationError("invalid name, '\\' not allowed")
    return name