from typing import List, Dict, Tuple
import asyncio
import tempfile
import json
import os
from sqlalchemy.orm import Session
from joule.models.data_store.data_store import DataStore
from joule.models.data_store.event_store import EventStore
from joule.models.data_movement.importing.importer import Importer
import shutil
import logging
log = logging.getLogger('joule')

# time to wait when uploaded_archives was empty after last check
IDLE_DELAY = 10
# time to wait after processing a file from uploaded_archives
PENDING_UPLOADS_DELAY = 5

class ImporterManager:
    def __init__(self, 
                 importers:Dict[str,Importer],
                 importer_data_directory:str,
                 event_store: EventStore,
                 data_store: DataStore,
                 db: Session):
        self.importers = importers
        self.importer_data_directory = importer_data_directory
        self.event_store = event_store
        self.data_store = data_store
        self.db = db
        self._stop_requested = False
        


    async def process_archive(self, metadata, archive_path)->List[Tuple[str,str]]:
        """Process an archive file and return the list of messages produced by the importer
           This will be a list like [('error','bad error message'),('info','just an info message'),...]
        """
        # create a directory to extract the archive to
        with (tempfile.TemporaryDirectory(dir=self.importer_data_directory) as tmpdirname):
            # use the metadata to find an appropriate importer
            # first try to find an importer specific to this node and archive name
            importer = self.importers.get((metadata['node'],metadata['name']), None)
            # second try to find an importer for this archive name but for any node
            if importer is None:
                importer = self.importers.get((None,metadata['name']), None)
            # if no matches, this archive cannot be processed
            if importer is None:
                msg = f"No importer defined for archive [{metadata['name']}] from node [{metadata['node']}]"
                log.warning(msg)
                return [('error',msg)]
            # unpack the archive and run the importer
            shutil.unpack_archive(archive_path,tmpdirname)
            return await importer.run(tmpdirname,
                                      db = self.db,
                                      data_store = self.data_store,
                                      event_store = self.event_store)
