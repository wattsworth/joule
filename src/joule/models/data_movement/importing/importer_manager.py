from typing import List
import asyncio
from sqlalchemy.orm import Session
from joule.models.data_movement.importing.importer import Importer
from joule.utilities import time_now

class ImporterManager:
    def __init__(self, 
                 importers:List[Importer]):
        self.importers = importers
        self._stop_requested = False

    async def _run(self):
        # iterate through the importers, running them as needed
        while not self._stop_requested:
            for importer in self.importers:
                await self.importer.run()
            await asyncio.sleep(1)

    async def start(self):
        self._task = asyncio.create_task(self._run())
        self._task.set_name("Importer Manager")

    async def stop(self):
        self._stop_requested = True
        await self._task
