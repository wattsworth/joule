from sqlalchemy.orm import relationship
from sqlalchemy import (Column, Integer, String,
                        Boolean, ForeignKey)
from sqlalchemy.dialects.postgresql import BIGINT
from typing import TYPE_CHECKING


from joule.models.meta import Base

if TYPE_CHECKING:
    from joule.models import (Folder)  # pragma: no cover


class EventStream(Base):
    """
    Attributes:
        name (str): stream name
        description (str): stream description
        decimate (bool): whether to store decimated data for event visualization
        folder (joule.Folder): parent Folder
        keep_us (int): microseconds of data to keep (KEEP_NONE=0, KEEP_ALL=-1).
    """
    __tablename__ = 'eventstream'
    __table_args__ = {"schema": "metadata"}

    id: int = Column(Integer, primary_key=True)
    name: str = Column(String, nullable=False)

    decimate: bool = Column(Boolean, default=True)

    KEEP_ALL = -1
    KEEP_NONE = 0
    keep_us: int = Column(BIGINT, default=KEEP_ALL)

    description: str = Column(String)
    folder_id: int = Column(Integer, ForeignKey('metadata.folder.id'))
    folder: "Folder" = relationship("Folder", back_populates="streams")

