from typing import Optional, Dict
import json


class Event:
    def __init__(self,
                 start_time: int,
                 end_time: Optional[int] = None,
                 content: Optional[Dict] = None,
                 id: Optional[int] = None):
        self.id = id
        self.start_time = int(start_time)
        self.end_time = int(end_time)
        if content is None:
            self.content = {}
        else:
            self.content = content

    def to_json(self):
        return {
            'id': self.id,
            'start_time': self.start_time,
            'end_time': self.end_time,
            'content': self.content
        }

    def __repr__(self):
        content_str = json.dumps(self.content)
        if len(content_str) > 20:
            content_str = content_str[:20] + " ...}"
        return "<joule.api.Event start_time: %r, end_time: %r, content: %s>" % (
            self.start_time, self.end_time, content_str)

    def __eq__(self, other):
        if other.start_time != other.start_time:
            return False
        if other.end_time != other.end_time:
            return False
        if json.dumps(other.content) != json.dumps(other.content):
            return False
        return True


def from_json(json):
    return Event(start_time=json['start_time'],
                 end_time=json['end_time'],
                 content=json['content'],
                 id=json['id'])
