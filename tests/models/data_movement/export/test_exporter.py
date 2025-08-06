import unittest
from unittest.mock import patch, AsyncMock, MagicMock
import os
import asyncio
import tempfile
import configparser

from joule.models.data_movement.targets import (DataTarget, EventTarget, ModuleTarget, ON_EVENT_CONFLICT)
from joule.models.data_movement.exporting.exporter import Exporter, exporter_from_config
import logging
logger = logging.getLogger('joule')

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
                                 retain_us=1,
                                 work_path=None,
                                 destination_url=None,
                                 destination_url_key=None,
                                 destination_folder=None,
                                 next_run_timestamp=0)

    async def test_processes_backlogs(self):
        with(tempfile.TemporaryDirectory() as work_path,
             tempfile.TemporaryDirectory() as destination_folder):
            self.exporter.work_path = work_path
            self.exporter.destination_folder = destination_folder
            self.exporter._initialize() # create folder structure
            # place backlog files
            # 1: only node
            # 2: only folder
            # 3: both node and folder
            
            with open(work_path+"/output/datasets/stub1.tgz", "w") as f:
                f.write("dataset_1")
            with open(work_path+"/output/datasets/stub2.tgz", "w") as f:
                f.write("dataset_2")
            with open(work_path+"/output/datasets/stub3.tgz", "w") as f:
                f.write("dataset_3")
            # create symlinks to mock failed exports
            os.symlink(work_path+"/output/datasets/stub1.tgz", work_path+"/output/node_backlog/stub1.tgz")
            os.symlink(work_path+"/output/datasets/stub2.tgz", work_path+"/output/folder_backlog/stub2.tgz")
            os.symlink(work_path+"/output/datasets/stub3.tgz", work_path+"/output/folder_backlog/stub3.tgz")
            os.symlink(work_path+"/output/datasets/stub3.tgz", work_path+"/output/node_backlog/stub3.tgz")

            await self.exporter.run(db="db_object", 
                                    event_store="event_store_object", 
                                    data_store="data_store_object",
                                    state_service=self.mock_state_service)
            # check that the targets were run
            self.event_target.run_export.assert_called()
            self.data_target.run_export.assert_called()
            self.module_target.run_export.assert_called()

            # check that the state was updated
            self.mock_state_service.save.assert_called()

            # check that the work path was cleaned up, all the output folders should be empty
            self.assertEqual(len(os.listdir(work_path+"/output/datasets")), 0)
            self.assertEqual(len(os.listdir(work_path+"/output/node_backlog")), 0)
            self.assertEqual(len(os.listdir(work_path+"/output/folder_backlog")), 0)

            # check that the export bundle is in the destination folder along with the stubbed backlogs
            output_files = os.listdir(destination_folder)
            self.assertEqual(len(output_files), 3)
            filenames = [os.path.basename(f) for f in output_files]
            self.assertIn("stub2.tgz", filenames)
            self.assertIn("stub3.tgz", filenames)
            # make sure the last file is the new data with a name like:
            # ww-data_YYYY_MM_DD-HH-MM-SS.tgz
            ww_data_file = [f for f in filenames if f.startswith("ww-data")][0]
            self.assertTrue(ww_data_file.endswith(".tgz"))

    async def test_runs_export_targets(self):
        with(tempfile.TemporaryDirectory() as work_path,
             tempfile.TemporaryDirectory() as destination_folder):
            self.exporter.work_path = work_path
            self.exporter.destination_folder = destination_folder
            await self.exporter.run(db="db_object", 
                                    event_store="event_store_object", 
                                    data_store="data_store_object",
                                    state_service=self.mock_state_service)
            # check that the targets were run
            self.event_target.run_export.assert_called()
            self.data_target.run_export.assert_called()
            self.module_target.run_export.assert_called()

            # check that the state was updated
            self.mock_state_service.save.assert_called()

            # check that the work path was cleaned up, all the output folders should be empty
            self.assertEqual(len(os.listdir(work_path+"/output/datasets")), 0)
            self.assertEqual(len(os.listdir(work_path+"/output/node_backlog")), 0)
            self.assertEqual(len(os.listdir(work_path+"/output/folder_backlog")), 0)

            # check that the export bundle is in the destination folder
            output_files = os.listdir(destination_folder)
            self.assertEqual(len(output_files), 1)
            self.assertTrue(output_files[0].endswith(".tgz"))

    async def test_cleans_directory(self):
        # expires datasets when the retain period is exceeded
        # place stub datasets in the backlog and run the export with the node
        # mocked to return an error so that all the data is retained
        # modify the retain time to be very short so that the datasets will be removed
        # check that the datasets and symlinks are removed from the backlog and the event is logged
        # only export to a folder, not a node


        self.exporter.destination_node = None
        with(tempfile.TemporaryDirectory() as work_path):
            self.exporter.work_path = work_path

            # disable exports to both the destination folder and node
            self.exporter.destination_folder = "/does/not/exist"
            self.exporter._export_to_node = MagicMock(return_value=False)

            self.exporter._initialize() # create folder structure
            # 1. place an old backlog file that will be expired
            with open(work_path+"/output/datasets/old_stub.tgz", "w") as f:
                f.write("old_stub")
            os.symlink(work_path+"/output/datasets/old_stub.tgz", work_path+"/output/node_backlog/old_stub.tgz")
            os.symlink(work_path+"/output/datasets/old_stub.tgz", work_path+"/output/folder_backlog/old_stub.tgz")
            # set the retain time to be short enough to expire old_stub.tgz
            self.exporter.backlog_us = 1e6
            await asyncio.sleep(1.1) # wait for the backlog time to expire

            # 2. place a dangling dataset file that will be removed
            with open(work_path+"/output/datasets/dangling_stub.tgz", "w") as f:
                f.write("dangling_stub")
            # 3. place an invalid file in the backlog (not a symlink)
            with open(work_path+"/output/node_backlog/not_a_symlink.tgz", "w") as f:
                f.write("not_a_symlink")
            # 4. place a symlink to an invalid location
            os.symlink("/etc/passwd", work_path+"/output/folder_backlog/external_symlink_location.tgz")
            os.symlink(work_path+"/output/datasets/invalid.err",
                       work_path+"/output/folder_backlog/invalid_symlink_location.tgz")
            # 5. place a symlink to a file outside of /datasets
            os.symlink("/etc/passwd", work_path+"/output/folder_backlog/invalid_symlink.tgz")
            logger.setLevel(logging.DEBUG)

            with self.assertLogs() as log:
                await self.exporter.run(db="db_object", 
                                        event_store="event_store_object", 
                                        data_store="data_store_object",
                                        state_service=self.mock_state_service)
            # check that the error was logged
            #for line in log.output:
            #    print(">   "+line)
            all_output = ''.join(log.output)
            self.assertIn("failed to copy", all_output)
            self.assertIn("failed to transmit", all_output)
            self.assertIn("dropping old_stub.tgz", all_output)
            self.assertIn("unexpected symlink", all_output) 
            self.assertIn("unexpected file", all_output)

            # run export again this time it should just keep the old export and have a new one
            # so there should be two files in /output/data and 2 matching symlinks in the backlog folders
            # set the retain time back up so the records do not expire
            self.exporter.backlog_us = 1000e6
            # wait over a second so the archive will have a different name
            await asyncio.sleep(1.1)
            with self.assertLogs() as log:
                await self.exporter.run(db="db_object", 
                                        event_store="event_store_object", 
                                        data_store="data_store_object",
                                        state_service=self.mock_state_service)
            
            # the node backlog should only have the new datasets, the old dataset and dangling dataset should be removed
            self.assertEqual(len(os.listdir(work_path+"/output/datasets")), 2)
            self.assertTrue(os.listdir(work_path+"/output/datasets")[0].startswith("ww-data"))
            self.assertTrue(os.listdir(work_path+"/output/datasets")[1].startswith("ww-data"))
            # again only the two new datasets should be in the folder backlog
            self.assertEqual(len(os.listdir(work_path+"/output/folder_backlog")), 2)
            self.assertTrue(os.listdir(work_path+"/output/folder_backlog")[0].startswith("ww-data"))
            self.assertTrue(os.listdir(work_path+"/output/folder_backlog")[1].startswith("ww-data"))
            # ...and in the node backlog
            self.assertEqual(len(os.listdir(work_path+"/output/node_backlog")), 2)
            self.assertTrue(os.listdir(work_path+"/output/node_backlog")[0].startswith("ww-data"))
            self.assertTrue(os.listdir(work_path+"/output/node_backlog")[1].startswith("ww-data"))

    def test_creates_exporter_from_config(self):
        # load the configuration file exporter.conf
        # check that the exporter is created with the correct parameters
        # check that the exporter can be run
        config = configparser.ConfigParser()
        config.read(EXPORTER_CONFIG)
        
        exporter = exporter_from_config(config=config, work_path="/workpath", node_name="test_node")
        self.assertEqual(exporter.name, "Sample Exporter")
        self.assertEqual(exporter.frequency_us, 60*60*1e6)
        self.assertEqual(exporter.backlog_us, -1)
        self.assertEqual(exporter.retain_us, int(5*7*24*60*60*1e6))
        self.assertEqual(len(exporter.data_targets), 1)

        data_target = exporter.data_targets[0]
        self.assertEqual(data_target.source_label, "data source")
        self.assertEqual(data_target.path, "/path/to/data_stream")
        self.assertEqual(data_target.decimation_factor,4)
        
        self.assertEqual(len(exporter.event_targets), 1)
        event_target = exporter.event_targets[0]
        self.assertEqual(event_target.source_label, "event source")
        self.assertEqual(event_target.path, "/path/to/event_stream")
        self.assertEqual(event_target.on_conflict, ON_EVENT_CONFLICT.NA)
        self.assertEqual(event_target.filter,[[["device","like","test%"]]])

        self.assertEqual(len(exporter.module_targets), 1)
        module_target = exporter.module_targets[0]
        self.assertEqual(module_target.source_label, "module name")
        self.assertIsNone(module_target.workspace_directory)
        self.assertEqual(module_target.module_name, "Example Module")