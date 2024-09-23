from typing import Optional, Dict
import json


class Event:
    def __init__(self,
                 start_time: int,
                 end_time: Optional[int] = None,
                 content: Optional[Dict] = None,
                 id: Optional[int] = None,
                 event_stream_id: Optional[int] = None,
                 node_name: Optional[str] = None):
        self.id = id
        self.start_time = int(start_time)
        self.end_time = int(end_time)
        # The two fields below are local to the API client and are needed
        # to distinguish events between different streams and nodes so that
        # write operations can be performed correctly- if an event has an ID
        # an update will be attempted but it is important that the ID corresponds
        # to the target table, if it has been copied from another stream this
        # could create an error where the update effectively erases an event
        # in the target table
        self.event_stream_id = event_stream_id
        self.node_name = node_name 
        if content is None:
            self.content = {}
        else:
            self.content = content

    def to_json(self, destination_node_name: str):
        # remove the ID fields if the event is not destined for the same node
        if self.node_name != destination_node_name:
            _id_value = None
            _event_stream_id_value = None
        else:
            _id_value = self.id
            _event_stream_id_value = self.event_stream_id
        return {
            'id': _id_value,
            'event_stream_id': _event_stream_id_value,
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
        if self.start_time != other.start_time:
            return False
        if self.end_time != other.end_time:
            return False
        if json.dumps(self.content) != json.dumps(other.content):
            return False
        return True


def from_json(json: dict, node_name: str):
    return Event(start_time=json['start_time'],
                 end_time=json['end_time'],
                 content=json['content'],
                 id=json['id'],
                 event_stream_id=json['event_stream_id'],
                 node_name=node_name)
