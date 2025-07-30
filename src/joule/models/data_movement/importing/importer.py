
from typing import TYPE_CHECKING, List

if TYPE_CHECKING:
    from joule.models.targets import EventTarget, DataTarget, ModuleTarget
"""
Configuration File:
[Main]
name = importer name

[DataStream.1]
source_label = source name
path = /path/to/stream
merge_gap = 5s

[EventStream.1]
source_label = source name
path = /path/to/stream
on_conflict = keep_source | keep_destination | keep_both | merge

[Module.1]
source_label = source name
module = <module_name>
parameters = ... <custom string passed to module>
"""

class Importer:

    def __init__(self, name, 
        event_targets: List['EventTarget'],
        module_targets: List['ModuleTarget'],
        data_targets: List['DataTarget']):

        self.event_targets = event_targets
        self.module_targets = module_targets
        self.data_targets = data_targets
        self.name = name

    async def run(self) -> bool:
        return True
    
def importer_from_config(config: dict, work_path: str) -> Importer:
    pass
