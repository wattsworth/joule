from sqlalchemy import Column, Integer, String

from joule.models.meta import Base


class Follower(Base):
    """
    Attributes:
        name (str): follower name
        key (str): API key for accessing the follower
        location (str): URL of the follower
    """
    __tablename__ = 'follower'
    __table_args__ = {"schema": "metadata"}

    id: int = Column(Integer, primary_key=True)
    name: str = Column(String, nullable=False, unique=True)
    key: str = Column(String, nullable=False, unique=True)
    location: str = Column(String, nullable=False, unique=True)

    def __repr__(self):
        return "<Follower(id=%r name=%r, location=%r, key=%r)>" % (
            self.id, self.name, self.location, self.key)

    def to_json(self):
        """
        Returns: Dictionary of Follower attributes
        """
        return {
            'id': self.id,
            'name': self.name,
            'location': self.location,
            'key': self.key
        }
