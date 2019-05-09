from sqlalchemy import Column, Integer, Enum, String, ForeignKey
import enum
import secrets

from joule.models.meta import Base


class Master(Base):
    """
    Attributes:
        name (str): master name
        type (Master.TYPE): whether the master is a user, joule, or lumen
        key (str): API key for accessing this node
    """
    __tablename__ = 'master'
    __table_args__ = {"schema": "metadata"}

    id: int = Column(Integer, primary_key=True)
    name: str = Column(String, nullable=False)
    key: str = Column(String, nullable=False, unique=True)

    class TYPE(enum.Enum):
        USER = enum.auto()
        JOULE_NODE = enum.auto()
        LUMEN_NODE = enum.auto()

    type: TYPE = Column(Enum(TYPE))
    grantor_id: int = Column(Integer, ForeignKey('metadata.master.id'))

    def __repr__(self):
        return "<Master(id=%r name=%r, type=%r, grantor_id=%r)>" % (
            self.id, self.name, self.type, self.grantor_id)

    def to_json(self):
        """
        Returns: Dictionary of Master attributes
        """
        return {
            'id': self.id,
            'name': self.name,
            'type': self.type.name,
            'grantor_id': self.grantor_id
        }


def make_key():
    # create an API key
    return secrets.token_urlsafe(32)
