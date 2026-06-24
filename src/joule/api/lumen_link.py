from dataclasses import dataclass
from typing import Optional, List
import json
import base64
import lzstring
from enum import StrEnum

from .session import BaseSession
from joule.api import Element, EventStream


class SettingType(StrEnum):
    FIXED="fixed"
    ATTRIBUTE="attribute"

class Axis(StrEnum):
    LEFT="left"
    RIGHT="right"

@dataclass
class BasicSetting:
    setting_type: SettingType
    value: str

    def to_json(self):
        return {
            'setting_type': self.setting_type,
            'value': self.value
        }

@dataclass
class SettingWithSize:
    setting_type: SettingType
    size: int
    value: str

    def to_json(self):
        return {
            'setting_type': self.setting_type,
            'value': self.value,
            'size': self.size
        }
    
@dataclass
class SettingWithAxis:
    setting_type: SettingType
    value: str|float
    axis: Axis

    def to_json(self):
        return {
            'setting_type': self.setting_type,
            'value': self.value,
            'axis': self.axis
        }
    

@dataclass
class DisplayedEventStream:
    event_stream: EventStream
    display_name: str = ""
    #NOTE: color does not support numeric setting
    color: Optional[BasicSetting] = None
    marker: Optional[SettingWithSize] = None
    label: Optional[SettingWithSize] = None
    position: Optional[SettingWithAxis] = None
    height: Optional[BasicSetting] = None
    # JSON filter syntax
    filter: Optional[List] = None

    def to_json(self):
        return {
            'id': self.event_stream.id,
            'display_name': self.display_name,
            'color': _setting(self.color),
            'marker': _setting(self.marker),
            'label': _setting(self.label),
            'position': _setting(self.position),
            'height': _setting(self.height),
            'filter': self.filter
        }

@dataclass
class DisplayedDataStreamElement:
    data_stream_element: Element
    display_name: str = ""
    color: str = ""
    axis: Optional[Axis] = None

    def to_json(self, stream_id):
        _axis = ''
        if self.axis is not None:
            _axis = self.axis.value
        return {
            'stream_id': stream_id,
            'index': self.data_stream_element.index,
            'display_name': self.display_name,
            'color': self.color,
            'axis': _axis.lower()
        }
    
@dataclass
class IRange:
    min: float
    max: float

    def to_json(self):
        # convert to UNIX milliseconds, required by Lumen frontend
        return{
            'min': self.min,
            'max': self.max
        }

def _setting(setting):
    if setting is None:
        return None
    else:
        return setting.to_json()
            
async def create_link(session: BaseSession,
                      lumen_url,
                      displayed_elements: DisplayedDataStreamElement,
                      displayed_event_streams: DisplayedEventStream,
                      nav_time_bounds: Optional[IRange],
                      main_time_bounds: Optional[IRange],
                      left_y_bounds: Optional[IRange],
                      right_y_bounds: Optional[IRange]):
    element_ids = [e.data_stream_element.id for e in displayed_elements]
    event_stream_ids = [e.event_stream.id for e in displayed_event_streams]
    joule_objects = await session.get("/folder/map.json",params=
                      {'data_stream_elements': json.dumps(element_ids),
                       'event_streams':json.dumps(event_stream_ids)})
    data_stream_element_map = joule_objects['data_stream_element_map']
    if nav_time_bounds is not None:
        nav_time_bounds.min /= 1e3
        nav_time_bounds.max /= 1e3 # convert to UNIX ms, required by Lumen frontend
    if main_time_bounds is not None:
        main_time_bounds.min /= 1e3
        main_time_bounds.max /= 1e3 # convert to UNIX ms, required by Lumen frontend
    # add in the plot settings
    resp = {
        'joule_objects': joule_objects,
        'elements': [e.to_json(stream_id=data_stream_element_map[str(e.data_stream_element.id)]) for e in displayed_elements],
        'event_streams': [e.to_json() for e in displayed_event_streams],
        'nav_time_bounds': _setting(nav_time_bounds),
        'main_time_bounds': _setting(main_time_bounds),
        'left_y_bounds': _setting(left_y_bounds),
        'right_y_bounds': _setting(right_y_bounds)
    }
    lz = lzstring.LZString()
    query_value = lz.compressToEncodedURIComponent(json.dumps(resp))
    return f"{lumen_url}/explorer?view={query_value}"