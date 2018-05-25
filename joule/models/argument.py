from sqlalchemy.orm import relationship
from sqlalchemy import (Column, Integer, String,
                        ForeignKey)
from typing import TYPE_CHECKING

from joule.models.meta import Base

if TYPE_CHECKING:
    from joule.models import Module


class Argument(Base):
    __tablename__ = 'argument'

    id: int = Column(Integer, primary_key=True)
    module_id: int = Column(Integer, ForeignKey('module.id'))
    module: 'Module' = relationship("Module", back_populates="arguments")
    name: str = Column(String, nullable=False)
    value: str = Column(String, nullable=False)

    def __repr__(self):
        return "<Argument name=%s value=%s>" % (self.name, self.value)

    def __str__(self):
        return "%s=%s" % (self.name, self.value)
