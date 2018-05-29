from sqlalchemy.orm import relationship, backref, Session
from sqlalchemy import Column, Integer, String, ForeignKey
from typing import List, TYPE_CHECKING
import logging
import pdb
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


class FolderError(Exception):
    pass


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
    pdb.set_trace()
    if len(path) == 0 or path[0] != '/':
        raise FolderError("invalid path [%s]" % path)
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
