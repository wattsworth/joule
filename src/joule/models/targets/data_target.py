from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from joule.models.data_store.data_store import DataStore
class DataTarget:
    def __init__(self, 
                 source_label: str,
                 path: str,
                 merge_gap: int = 0,
                 decimation_factor: int = 1):
        self.source_label = source_label
        self.path = path
        self.merge_gap = merge_gap
        self.decimation_factor = decimation_factor

    async def run_export(self,
                         store: 'DataStore', 
                         target_directory: str, 
                         last_ts: int) -> tuple[int, dict]:
        return 0,{}
    
    async def run_import(self,
                         store: 'DataStore',
                         metadata: dict,
                         source_directory: str) -> bool:
        return True