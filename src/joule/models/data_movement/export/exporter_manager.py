from typing import List
import asyncio
from sqlalchemy.orm import Session
from joule.models.data_movement.export.exporter import Exporter
from joule.models.data_movement.export.exporter_state import ExporterStateService
from joule.utilities import time_now

class ExporterManager:
    def __init__(self, 
                 exporters:List[Exporter],
                 state_service: ExporterStateService):
        self.exporters = exporters
        self.state_service = state_service
        self._stop_requested = False

    async def _run(self):
        # compute the initial next_run_timestamp for each exporter
        for exporter in self.exporters:
            state = self.state_service.get(exporter_name=exporter.name, 
                                            source_type='exporter', 
                                            source_label="")
            exporter.next_run_timestamp = state.last_timestamp + exporter.interval

        # iterate through the exporters, running them as needed
        while not self._stop_requested:
            for exporter in self.exporters:
                now = time_now()
                if now >= exporter.next_run_timestamp:
                    state = await exporter.run(self.state_service)
                    self.state_service.save(exporter_name=self.name, 
                                       source_type='exporter', 
                                       source_label="", state=state)
                    exporter.next_run_timestamp = now + exporter.interval
            asyncio.sleep(1)

    async def start(self):
        self._task = asyncio.create_task(self._run())
        self._task.set_name("Exporter Manager")

    async def stop(self):
        self._stop_requested = True
        await self._task
