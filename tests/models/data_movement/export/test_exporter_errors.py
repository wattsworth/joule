import unittest
from unittest.mock import patch, AsyncMock, MagicMock
import os
import tempfile
from joule.models.data_movement.targets import (DataTarget, EventTarget, ModuleTarget, ON_EVENT_CONFLICT)
from joule.models.data_movement.export.exporter import Exporter

class TestExporter(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.event_target = EventTarget(source_label="source1", path="/path1", filter="filter1", 
                                   on_conflict=ON_EVENT_CONFLICT.KEEP_BOTH)
        self.event_target.run_export = AsyncMock()
        self.data_target = DataTarget(source_label="source2", path="/path2")
        self.data_target.run_export = AsyncMock()
        self.module_target = ModuleTarget(source_label="source3", module_directory="/path3", config_parameters="params")
        self.module_target.run_export = AsyncMock()

        self.mock_node = AsyncMock()

        self.mock_state_service = MagicMock()
        self.mock_state_service.get = MagicMock(return_value=0)
        self.mock_state_service.set = MagicMock()
        
        self.exporter = Exporter(name="test",
                                 event_targets=[self.event_target],
                                 module_targets=[self.module_target],
                                 data_targets=[self.data_target],
                                 frequency_us=1,
                                 backlog_us=1,
                                 retain_us=1,
                                 work_path=None,
                                 destination_node=self.mock_node,
                                 destination_folder=None,
                                 next_run_timestamp=0)
        
    async def test_saves_backlog_on_folder_export_error(self):
        # only export to a folder, not a node
        self.exporter.destination_node = None
        with(tempfile.TemporaryDirectory() as work_path,
             tempfile.TemporaryDirectory() as destination_folder):
            # remove write permissions from destiantion folder to create an error condition
            os.chmod(destination_folder, 0o400)
            self.exporter.work_path = work_path
            self.exporter.destination_folder = destination_folder
            with self.assertLogs() as log:
                await self.exporter.run(db="db_object", 
                                        event_store="event_store_object", 
                                        data_store="data_store_object",
                                        state_service=self.mock_state_service)
            # check that the error was logged
            self.assertIn("failed to copy", log.output[0])
            # check that the targets were run
            self.event_target.run_export.assert_called()
            self.data_target.run_export.assert_called()
            self.module_target.run_export.assert_called()

            # check that the state was updated
            self.mock_state_service.save.assert_called()

            # the node backlog should be empty
            self.assertEqual(len(os.listdir(work_path+"/output/node_backlog")), 0)

            # the dataset should be saved
            self.assertEqual(len(os.listdir(work_path+"/output/datasets")), 1)
            backlogged_dataset = work_path+"/output/folder_backlog/"+os.listdir(work_path+"/output/folder_backlog")[0]
            self.assertTrue(backlogged_dataset.endswith(".tgz"))

            # a symlink should be created in the folder backlog
            self.assertEqual(len(os.listdir(work_path+"/output/folder_backlog")), 1)
            dataset_symlink =work_path+"/output/folder_backlog/"+os.listdir(work_path+"/output/folder_backlog")[0]
            self.assertTrue(dataset_symlink.endswith(".tgz"))

            # make sure this file is a symlink and points to the dataset
            self.assertTrue(os.path.islink(dataset_symlink))
            self.assertEqual(os.stat(dataset_symlink).st_ino, os.stat(backlogged_dataset).st_ino)
            self.assertEqual(os.stat(dataset_symlink).st_dev, os.stat(backlogged_dataset).st_dev)

            # check that the export bundle is not in the destination folder
            self.assertEqual(len(os.listdir(destination_folder)), 0)
