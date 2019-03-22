from sqlalchemy import Column, Integer, Enum, String, ForeignKey
import enum

from joule.models.meta import Base


class Follower(Base):
    """
    Attributes:
        name (str): follower name
        key (str): API key for accessing the follower
        location (str): URL of the follower
    """
    __tablename__ = 'master'
    __table_args__ = {"schema": "metadata"}

    id: int = Column(Integer, primary_key=True)
    name: str = Column(String, nullable=False, unique=True)
    key: str = Column(String, nullable=False, unique=True)

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
