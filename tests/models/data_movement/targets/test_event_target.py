import unittest
from unittest.mock import patch, MagicMock, AsyncMock
import tempfile
from joule.models.data_movement.targets.event_target import EventTarget, event_target_from_config
from joule.models.data_movement.exporting.exporter_state import ExporterState
from joule.models import EventStream
from tests import helpers
import json
import os
from joule.models.pipes.local_pipe import LocalPipe
import numpy as np

class TestEventTarget(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        LAYOUT = "int64_2"
        LENGTH = 500
        self.chunk1 = helpers.create_data(LAYOUT, length=LENGTH)
        self.chunk2 = helpers.create_data(LAYOUT, length=LENGTH, 
                                     start = self.chunk1['timestamp'][-1]+100)
        self.my_pipe = LocalPipe("int64_2")
        self.my_pipe.write_nowait(self.chunk1)
        self.my_pipe.close_interval_nowait()
        self.my_pipe.write_nowait(self.chunk2)
        self.my_pipe.close_nowait()

        self.my_stream = EventStream(
            name="test",
            description="test_description",
            event_fields = {"name": "string", 
                            "description": "test name"})
        self.my_stream.touch()

    async def test_event_target_from_config(self):
        pass