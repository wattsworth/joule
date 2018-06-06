from sqlalchemy import (Column, Integer, String,
                        Enum, DateTime)
import enum

from joule.models.meta import Base


class LogEntry(Base):
    __tablename__ = 'log_entry'
    id: int = Column(Integer, primary_key=True)
    module_id: int = Column(Integer)
    timestamp: DateTime = Column(DateTime, nullable=False)
    message: str = Column(String)

    class SOURCE(enum.Enum):
        STDOUT = enum.auto()
        STDERR = enum.auto()
    source: SOURCE = Column(Enum(SOURCE))

    def __repr__(self):
        return "<LogEntry timestamp=%r message=%s source=%r>" % \
               (self.timestamp, self.message, self.source)

    def __str__(self):
        return self.message