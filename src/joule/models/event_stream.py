from sqlalchemy.orm import relationship, Mapped
from sqlalchemy import (Column, Integer, String, DateTime, ForeignKey)
from sqlalchemy.dialects.postgresql import BIGINT, JSONB
from typing import TYPE_CHECKING, Dict, Optional
import datetime
from sqlalchemy_utils import force_instant_defaults

from joule.errors import ConfigurationError
from joule.models.meta import Base
from joule.utilities.validators import validate_event_fields

if TYPE_CHECKING:
    from joule.models import (Folder)  # pragma: no cover
    from joule.models.data_store.event_store import StreamInfo

force_instant_defaults()


class EventStream(Base):
    """
    Attributes:
        name (str): stream name
        description (str): stream description
        decimate (bool): whether to store decimated data for event visualization
        folder (joule.Folder): parent Folder
        chunk_duration_us (int): chunk duration in microseconds, 0 for normal table
        keep_us (int): microseconds of data to keep (KEEP_NONE=0, KEEP_ALL=-1).
    """
    __tablename__ = 'eventstream'
    __table_args__ = {"schema": "metadata"}

    id: int = Column(Integer, primary_key=True)
    name: str = Column(String, nullable=False)
    event_fields: Dict[str, str] = Column(JSONB)
    chunk_duration_us: int = Column(BIGINT, default=0)

    KEEP_ALL = -1
    KEEP_NONE = 0
    keep_us: int = Column(BIGINT, default=KEEP_ALL)

    description: str = Column(String)
    folder_id: int = Column(Integer, ForeignKey('metadata.folder.id'), nullable=False)
    folder: Mapped["Folder"] = relationship("Folder", back_populates="event_streams")
    updated_at: datetime.datetime = Column(DateTime, nullable=False)

    def update_attributes(self, attrs: Dict) -> None:
        updated = False
        if 'name' in attrs:
            self.name = validate_name(attrs['name'])
            updated = True
        if 'description' in attrs:
            self.description = attrs['description']
            updated = True
        if 'event_fields' in attrs:
            self.event_fields = validate_event_fields(attrs['event_fields'])
            updated = True
        if 'chunk_duration_us' in attrs:
            self.chunk_duration_us = validate_chunk_duration(attrs['chunk_duration_us'])
            updated = True
        if 'keep_us' in attrs:
            self.keep_us = validate_keep_us(attrs['keep_us'])
            updated = True
        if updated:
            self.touch()

    # update timestamps on all folders in hierarchy
    def touch(self, now: Optional[datetime.datetime] = None) -> None:
        if now is None:
            now = datetime.datetime.utcnow()
        self.updated_at = now
        if self.folder is not None:
            self.folder.touch(now)

    def to_json(self, info: Dict[int, 'StreamInfo'] = None) -> Dict:
        """
          Args:
            info: optional content added to ``data_info`` field

        Returns: Dictionary of DataStream attributes

        """

        resp = {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'event_fields': self.event_fields,
            'chunk_duration_us': self.chunk_duration_us,
            'keep_us': self.keep_us,
            'updated_at': self.updated_at.isoformat()
        }

        if info is not None and self.id in info:
            resp['data_info'] = info[self.id].to_json()
        return resp

    def __str__(self):
        return "EventStream [{name}]".format(name=self.name)

    def __repr__(self):
        return "<EventStream(id=%r, name='%s')>" % (self.id, self.name)


def from_json(data: Dict) -> EventStream:
    """
    Construct an EventStream from a dictionary of attributes produced by
    :meth:`EventStream.to_json`

    Args:
        data: attribute dictionary

    Returns: EventStream

    """

    return EventStream(id=data["id"],
                       name=validate_name(data["name"]),
                       description=data["description"],
                       event_fields=validate_event_fields(data["event_fields"]),
                       chunk_duration_us=validate_chunk_duration(data["chunk_duration_us"]),
                       keep_us=validate_keep_us(data["keep_us"]),
                       updated_at=datetime.datetime.utcnow()
                       )


def validate_chunk_duration(duration):
    try:
        duration = int(duration)
    except (ValueError, TypeError):
        raise ConfigurationError("invalid chunk_duration_us, must be an integer")
    if duration < 0:
        raise ConfigurationError("invalid chunk_duration_us, must be > 0")
    return duration


def validate_keep_us(keep_us):
    try:
        keep_us = int(keep_us)
    except (ValueError, TypeError):
        raise ConfigurationError("invalid keep_us, must be an integer")
    if keep_us < -1:
        raise ConfigurationError("invalid keep_us, must be -1 (KEEP_ALL) or >= 0")
    return keep_us




def validate_name(name: str) -> str:
    if name is None or len(name) == 0:
        raise ConfigurationError("missing name")
    if '/' in name:
        raise ConfigurationError("invalid name, '\\' not allowed")
    return name
