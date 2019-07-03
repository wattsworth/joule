from sqlalchemy.orm import relationship
from sqlalchemy import Column, Integer, String, ForeignKey, types
import datetime

from joule.models.meta import Base
from joule.errors import ApiError


class Annotation(Base):
    """
    Attributes:
        title (str): title of the annotation
        content (str): a longer description if necessary
        start (date): the time of the event
        end (date): if the annotation is a range, the end time
    """
    __tablename__ = 'annotation'
    __table_args__ = {"schema": "metadata"}

    id: int = Column(Integer, primary_key=True)
    title: str = Column(String)
    content: str = Column(String)
    start: datetime = Column(types.TIMESTAMP, nullable=False)
    end: datetime = Column(types.TIMESTAMP, default=None)

    stream_id: int = Column(Integer, ForeignKey('metadata.stream.id'))
    stream: 'Stream' = relationship("Stream", back_populates="annotations")

    def __repr__(self):
        return "<Annotation(title='%s', content='%s', stream_id=%s)>" % (self.title, self.content, self.stream_id)

    def to_json(self):
        json = {
            'id': self.id,
            'title': self.title,
            'content': self.content,
            'start': int(self.start.replace(tzinfo=datetime.timezone.utc).timestamp() * 1e6),
            'stream_id': self.stream_id
        }
        if self.end is not None:
            json['end'] = int(self.end.replace(tzinfo=datetime.timezone.utc).timestamp() * 1e6)
        else:
            json['end'] = None
        return json

    def update_attributes(self, json):
        if 'title' in json:
            self.title = json['title']
        if 'content' in json:
            self.content = json['content']


def from_json(json):
    try:
        my_annotation = Annotation(title=json['title'])
        ts = float(json['start'])
        my_annotation.start = datetime.datetime.utcfromtimestamp(ts / 1e6)
        if 'end' in json and json['end'] is not None:
            ts = float(json['end'])
            my_annotation.end = datetime.datetime.utcfromtimestamp(ts / 1e6)
        if 'content' in json:
            my_annotation.content = json['content']
    except (ValueError, KeyError, TypeError):
        raise ApiError("invalid values for annotation")
    return my_annotation
