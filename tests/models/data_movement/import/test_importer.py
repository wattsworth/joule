import unittest
from unittest.mock import patch, AsyncMock, MagicMock
import os
import asyncio
import tempfile
import configparser

from joule.models.data_store.data_store import DataStore
from joule.models.data_store.event_store import EventStore
from joule.models.data_movement.targets import (DataTarget, EventTarget, ModuleTarget, ON_EVENT_CONFLICT)
from joule.models.data_movement.importing.importer import Importer, importer_from_config
import logging
logger = logging.getLogger('joule')

IMPORTER_CONFIG = os.path.join(os.path.dirname(__file__),'importer.conf')
ARCHIVE_PATH = os.path.join(os.path.dirname(__file__), '..','archive_data')

class TestImporter(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.event_target = EventTarget(source_label="simple_events", path="/path1", filter="filter1", 
                                   on_conflict=ON_EVENT_CONFLICT.KEEP_BOTH)
        self.event_target.run_import = AsyncMock()
        self.data_target = DataTarget(source_label="random", path="/path2")
        self.data_target.run_import = AsyncMock()
        self.module_target = ModuleTarget(source_label="source3", 
                                          module_name="module1",
                                          workspace_directory="/path3",
                                          config_parameters="params")
        self.module_target.run_import = AsyncMock()
        self.mock_event_store = MagicMock(EventStore)
        self.mock_data_store = MagicMock(DataStore)

        
        self.importer = Importer(name="test",
                                 node_name="test_node",
                                 event_targets={self.event_target.source_label:self.event_target},
                                 module_targets={self.module_target.source_label:self.module_target},
                                 data_targets={self.data_target.source_label:self.data_target})

    async def test_runs_import_targets(self):
        logger = await self.importer.run(path=ARCHIVE_PATH,
                                data_store=self.mock_data_store,
                                event_store=self.mock_event_store,
                                db = None)
        self.data_target.run_import.assert_called_once()
        self.event_target.run_import.assert_called_once()
        # this archive has an event stream and two data streams, only one of the data streams
        # matches a target in this importer so check the logs to verify there is 
        # a warning message
        self.assertFalse(logger.success)
        warning = logger.warning_messages[0]
        self.assertIn("data stream with label [filtered]", warning.message)

    def test_creates_importer_from_config(self):
        # load the configuration file importer.conf
        # check that the importer is created with the correct parameters
        # check that the importer can be run
        config = configparser.ConfigParser()
        config.read(IMPORTER_CONFIG)
        
        importer = importer_from_config(config=config)
        self.assertEqual(importer.name, "Sample Importer")
        self.assertEqual(len(importer.data_targets), 1)

        data_target = importer.data_targets['data source']
        self.assertEqual(data_target.source_label, "data source")
        self.assertEqual(data_target.path, "/path/to/data_stream")
        
        self.assertEqual(len(importer.event_targets), 1)
        event_target = importer.event_targets['event source']
        self.assertEqual(event_target.source_label, "event source")
        self.assertEqual(event_target.path, "/path/to/event_stream")
        self.assertEqual(event_target.on_conflict, ON_EVENT_CONFLICT.KEEP_SOURCE)

        self.assertEqual(len(importer.module_targets), 1)
        module_target = importer.module_targets['module name']
        self.assertEqual(module_target.source_label, "module name")
        self.assertIsNone(module_target.workspace_directory)
        self.assertEqual(module_target.module_name, "test_module")
        self.assertEqual(module_target.config_parameters,"custom parameters")
        
