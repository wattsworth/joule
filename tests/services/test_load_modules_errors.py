import unittest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

import logging
import tempfile
import os

from joule.models import Base
from joule.services import load_modules

logger = logging.getLogger('joule')


class TestLoadModulesErrors(unittest.TestCase):
    def setUp(self):
        # create a database
        engine = create_engine('sqlite://')
        Base.metadata.create_all(engine)
        self.db = Session(bind=engine)

    def test_module_must_have_exec_cmd(self):
        conf_str = """
                            [Main]
                            name=bad module
                            [Inputs]
                            input=/path/to/input:float32[y]
                            [Outputs]
                            output=/path/to/output:float32[x]
                            """
        with self.assertLogs(level="ERROR") as logs:
            attempt_load(conf_str, self.db)
        all_logs = ' '.join(logs.output).lower()
        self.assertTrue('exec_cmd' in all_logs)

    def test_outputs_section_required(self):
        conf_str = """
                    [Main]
                    name=bad module
                    exec_cmd=runit.sh
                    [Inputs]
                    input=/path/to/input
                    """
        with self.assertLogs(level="ERROR") as logs:
            attempt_load(conf_str, self.db)
        all_logs = ' '.join(logs.output).lower()
        self.assertTrue('outputs' in all_logs)

    def test_inputs_section_required(self):
        conf_str = """
                    [Main]
                    name=bad module
                    exec_cmd=runit.sh
                    [Outputs]
                    output=/path/to/output:int64[x,y,z]
                    """
        with self.assertLogs(level="ERROR") as logs:
            attempt_load(conf_str, self.db)
        all_logs = ' '.join(logs.output).lower()
        self.assertTrue('inputs' in all_logs)

    def test_streams_must_be_configured(self):
        conf_str = """
                    [Main]
                    name=bad module
                    exec_cmd=runit.sh
                    [Outputs]
                    output=/path/not/configured
                    [Inputs]
                    # none
                    """
        with self.assertLogs(level="ERROR") as logs:
            attempt_load(conf_str, self.db)
        all_logs = ' '.join(logs.output).lower()
        self.assertTrue('configured' in all_logs)


def attempt_load(conf_str, db: Session):
    with tempfile.TemporaryDirectory() as conf_dir:
        with open(os.path.join(conf_dir, "invalid.conf"), 'w') as f:
            f.write(conf_str)
        load_modules.run(conf_dir, db)
