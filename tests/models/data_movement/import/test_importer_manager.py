import unittest
from unittest.mock import patch, AsyncMock, MagicMock
import os
import shutil
import tempfile
import asyncio
from joule.models.data_store.data_store import DataStore
from joule.models.data_store.event_store import EventStore

from joule.models.data_movement.importing.importer_manager import ImporterManager
from joule.models.data_movement.importing.importer import Importer
from joule.models.data_movement.targets import DataTarget, EventTarget
from joule.utilities import archive_tools
import logging
logger = logging.getLogger('joule')

ARCHIVES_PATH = os.path.join(os.path.dirname(__file__), '../../../cli/archive/archives')
ARCHIVES = ["ww-data_2025_09_03-10-03-29.zip",
            "ww-data_2025_09_03-10-03-59.zip"]
class TestImporterManager(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.importer_inbox_directory = os.path.join(tempfile.mkdtemp(prefix="inbox"),"archives")
        self.importer_data_directory = tempfile.mkdtemp(prefix="datadir")
        self.uploaded_archives = [os.path.join(ARCHIVES_PATH,name) for name in ARCHIVES]
        shutil.copytree(ARCHIVES_PATH, self.importer_inbox_directory)


    async def test_unpacks_archives(self):
        random_target = MagicMock(DataTarget)
        filtered_target = MagicMock(DataTarget)
        unused_target = MagicMock(DataTarget)
        unused_importer = MagicMock(Importer)
        event_target = MagicMock(EventTarget)
        importers = {
            ('joule-dev','all_data'):
                Importer(node_name='joule-dev',
                        name='all_data',
                        event_targets={
                            'simple_events': event_target,
                            'unused': unused_target
                        },
                        data_targets={
                            'random': random_target,
                            'filtered': filtered_target,
                            'unused': unused_target},
                        module_targets={}),
            ('joule-dev','unmatched'):
                unused_importer
        }
        importer_manager = ImporterManager(importers=importers,
                                           importer_data_directory=self.importer_data_directory,
                                           data_store=MagicMock(DataStore),
                                           event_store=MagicMock(EventStore),
                                           db=None)
        # just process the first archive
        archive_path = self.uploaded_archives[0]
        metadata = archive_tools.read_metadata(archive_path)
        await importer_manager.process_archive(metadata, archive_path)
        # filtered and random are data streams in the archive
        random_target.run_import.assert_called_once()
        filtered_target.run_import.assert_called_once()
        # simple_events is an event stream in the archive
        event_target.run_import.assert_called()
        # the archive is named 'all_data' so this importer is not used
        unused_importer.run.assert_not_called()
        # there is no data stream or event stream labeled 'unused' so this does not run
        unused_target.run_import.assert_not_called()

    async def test_fallback_to_match_archive(self):
        random_target = MagicMock(DataTarget)
        filtered_target = MagicMock(DataTarget)
        unused_target = MagicMock(DataTarget)
        unused_importer = MagicMock(Importer)
        event_target = MagicMock(EventTarget)
        importers = {
            (None,'all_data'):
                Importer(node_name='joule-dev',
                        name='all_data',
                        event_targets={
                            'simple_events': event_target,
                            'unused': unused_target
                        },
                        data_targets={
                            'random': random_target,
                            'filtered': filtered_target,
                            'unused': unused_target},
                        module_targets={}),
            ('joule-dev','unmatched'):
                unused_importer
        }
        importer_manager = ImporterManager(importers=importers,
                                           importer_data_directory=self.importer_data_directory,
                                           data_store=MagicMock(DataStore),
                                           event_store=MagicMock(EventStore),
                                           db=None)
        # just process the first archive
        archive_path = self.uploaded_archives[0]
        metadata = archive_tools.read_metadata(archive_path)
        await importer_manager.process_archive(metadata, archive_path)
        # filtered and random are data streams in the archive
        random_target.run_import.assert_called_once()
        filtered_target.run_import.assert_called_once()
        # simple_events is an event stream in the archive
        event_target.run_import.assert_called()
        # the archive is named 'all_data' so this importer is not used
        unused_importer.run.assert_not_called()
        # there is no data stream or event stream labeled 'unused' so this does not run
        unused_target.run_import.assert_not_called()

    async def test_warning_if_unmatched_importer(self):
        importers = {
            ('joule-dev','unmatched'): None # not used
        }
        importer_manager = ImporterManager(importers=importers,
                                           importer_data_directory=self.importer_data_directory,
                                           data_store=MagicMock(DataStore),
                                           event_store=MagicMock(EventStore),
                                           db=None)
        # just process the first archive
        archive_path = self.uploaded_archives[0]
        metadata = archive_tools.read_metadata(archive_path)
        with self.assertLogs() as logs:
            await importer_manager.process_archive(metadata, archive_path)
        self.assertIn("No importer defined for archive", ''.join(logs.output))


    def tearDown(self):
        shutil.rmtree(self.importer_inbox_directory)
        shutil.rmtree(self.importer_data_directory)
        return super().tearDown()