from typing import List
import asyncio
from sqlalchemy.orm import Session
from joule.models.data_movement.exporting.exporter import Exporter
from joule.models.data_movement.exporting.exporter_state import ExporterState, ExporterStateService
from joule.utilities import time_now, timestamp_to_human
from joule.models.data_store.data_store import DataStore
from joule.models.data_store.event_store import EventStore

class ExporterManager:
    def __init__(self, 
                 exporters:List[Exporter],
                 state_service: ExporterStateService,
                 event_store: EventStore,
                 data_store: DataStore,
                 db: Session):
        self.exporters = exporters
        self.state_service = state_service
        self.event_store = event_store
        self.data_store = data_store
        self.db = db
        self._stop_requested = False
        # validate that all the exporter targets exist on this node
        for exporter in exporters:
            exporter.validate(db)


    async def _run(self):
        # compute the initial next_run_timestamp for each exporter
        for exporter in self.exporters:
            state = self.state_service.get(exporter_name=exporter.name, 
                                            source_type='exporter')
            # if the exporter has never run, schedule it for immediate execution
            if state.last_timestamp is None:
                exporter.next_run_timestamp = time_now()
            else:
                exporter.next_run_timestamp = state.last_timestamp + exporter.frequency_us
                print(f"last run of exporter [{exporter.name}] at {timestamp_to_human(state.last_timestamp)}")
            print(f"scheduling exporter [{exporter.name}] to run at {timestamp_to_human(exporter.next_run_timestamp)}")
        # iterate through the exporters, running them as needed
        while not self._stop_requested:
            for exporter in self.exporters:
                now = time_now()
                if now >= exporter.next_run_timestamp:
                    print(f"{timestamp_to_human(exporter.next_run_timestamp)}: running exporter [{exporter.name}]...")
                    await exporter.run(event_store=self.event_store,
                                       data_store=self.data_store,
                                       state_service=self.state_service,
                                       db=self.db)
                    self.state_service.save(exporter_name=exporter.name, 
                                       source_type='exporter',
                                       source_label="",
                                       state=ExporterState(last_timestamp=now))
                    exporter.next_run_timestamp = now + exporter.frequency_us
                    print(f"\tNext run scheduled for {timestamp_to_human(exporter.next_run_timestamp)}")
            self.db.commit()
            await asyncio.sleep(1)

    async def start(self):
        self._task = asyncio.create_task(self._run())
        self._task.set_name("Exporter Manager")

    async def stop(self):
        self._stop_requested = True
        await self._task
