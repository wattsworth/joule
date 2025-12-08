import unittest
from unittest.mock import patch, AsyncMock, MagicMock
import os
import tempfile
import configparser
from joule.models.data_movement.targets import (DataTarget, EventTarget, ModuleTarget, ON_EVENT_CONFLICT)
from joule.models.data_movement.exporting.exporter import Exporter, exporter_from_config

EXPORTER_CONFIG = os.path.join(os.path.dirname(__file__),'exporter.conf')

class TestExporter(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.event_target = EventTarget(source_label="source1", path="/path1", filter="filter1", 
                                   on_conflict=ON_EVENT_CONFLICT.KEEP_BOTH)
        self.event_target.run_export = AsyncMock()
        self.data_target = DataTarget(source_label="source2", path="/path2")
        self.data_target.run_export = AsyncMock()
        self.module_target = ModuleTarget(source_label="source3",
                                          module_name="module1",
                                          workspace_directory="/path3", 
                                          config_parameters="params")
        self.module_target.run_export = AsyncMock()

        self.mock_state_service = MagicMock()
        self.mock_state_service.get = MagicMock(return_value=0)
        self.mock_state_service.set = MagicMock()
        
        self.exporter = Exporter(name="test",
                                 node_name="test_node",
                                 event_targets=[self.event_target],
                                 module_targets=[self.module_target],
                                 data_targets=[self.data_target],
                                 frequency_us=1,
                                 backlog_us=100e6,
                                 retain_us=100e6,
                                 work_path=None,
                                 destination_url=None,
                                 destination_url_key=None,
                                 destination_folder=None,
                                 next_run_timestamp=0)
        
    async def test_saves_backlog_on_folder_export_error(self):
        # only export to a folder, not a node
        self.exporter.destination_node = None
        with(tempfile.TemporaryDirectory() as work_path,
             tempfile.TemporaryDirectory() as destination_folder):
            # remove write permissions from destination folder to create an error condition
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
            self.assertTrue(backlogged_dataset.endswith(".zip"))

            # a symlink should be created in the folder backlog
            self.assertEqual(len(os.listdir(work_path+"/output/folder_backlog")), 1)
            dataset_symlink =work_path+"/output/folder_backlog/"+os.listdir(work_path+"/output/folder_backlog")[0]
            self.assertTrue(dataset_symlink.endswith(".zip"))

            # make sure this file is a symlink and points to the dataset
            self.assertTrue(os.path.islink(dataset_symlink))
            self.assertEqual(os.stat(dataset_symlink).st_ino, os.stat(backlogged_dataset).st_ino)
            self.assertEqual(os.stat(dataset_symlink).st_dev, os.stat(backlogged_dataset).st_dev)

            # check that the export bundle is not in the destination folder
            self.assertEqual(len(os.listdir(destination_folder)), 0)

    async def test_saves_backlog_on_node_export_error(self):
        # only export to a node, not a folder
        self.exporter.destination_url = "http://nowhere"
        self.exporter._export_to_node = AsyncMock(return_value=False)
        with(tempfile.TemporaryDirectory() as work_path):
            self.exporter.work_path = work_path
            with self.assertLogs() as log:
                await self.exporter.run(db="db_object", 
                                        event_store="event_store_object", 
                                        data_store="data_store_object",
                                        state_service=self.mock_state_service)
            # check that the error was logged
            self.assertIn("failed to transmit", log.output[0])
            # check that the targets were run
            self.event_target.run_export.assert_called()
            self.data_target.run_export.assert_called()
            self.module_target.run_export.assert_called()

            # check that the state was updated
            self.mock_state_service.save.assert_called()

            # the folder backlog should be empty
            self.assertEqual(len(os.listdir(work_path+"/output/folder_backlog")), 0)

            # the dataset should be saved
            self.assertEqual(len(os.listdir(work_path+"/output/datasets")), 1)
            backlogged_dataset = work_path+"/output/node_backlog/"+os.listdir(work_path+"/output/node_backlog")[0]
            self.assertTrue(backlogged_dataset.endswith(".zip"))

            # a symlink should be created in the node backlog
            self.assertEqual(len(os.listdir(work_path+"/output/node_backlog")), 1)
            dataset_symlink =work_path+"/output/node_backlog/"+os.listdir(work_path+"/output/node_backlog")[0]
            self.assertTrue(dataset_symlink.endswith(".zip"))

            # make sure this file is a symlink and points to the dataset
            self.assertTrue(os.path.islink(dataset_symlink))
            self.assertEqual(os.stat(dataset_symlink).st_ino, os.stat(backlogged_dataset).st_ino)
            self.assertEqual(os.stat(dataset_symlink).st_dev, os.stat(backlogged_dataset).st_dev)

    async def test_invalid_exporter_config(self):
        # load the configuration file exporter.conf
        # check that the exporter is created with the correct parameters
        # check that the exporter can be run
        config = configparser.ConfigParser()
        config.read(EXPORTER_CONFIG)
        del config['Main']['name'] # remove the name to make the exporter invalid
        with self.assertRaises(ValueError) as e:
            exporter_from_config(config=config, work_path="/workpath", node_name="test_node")
        self.assertIn("missing 'name'", str(e.exception))