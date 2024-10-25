from sqlalchemy import Column, String, UUID
import uuid as uuid_type
from joule.models.meta import Base


class Node(Base):
    """
    Attributes:
        id (uuid): globally unique identifier, not visible to user
        private_key (str): --not used yet--
        public_key (str): --not used yet--
    """
    __tablename__ = 'node'
    __table_args__ = {"schema": "metadata"}

    uuid: uuid_type.UUID = Column("uuid", UUID(as_uuid=True), primary_key=True, default=uuid_type.uuid4, unique=True)
    private_key: str = Column(String)
    public_key: str = Column(String)
    version: str = Column(String)

    