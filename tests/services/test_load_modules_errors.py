import unittest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

import logging
import tempfile
import os

from tests.helpers import DbTestCase
from joule.services import load_modules

logger = logging.getLogger('joule')

class TestLoadModulesErrors(DbTestCase):

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
        self.assertIn('exec_cmd', all_logs)

    def test_streams_must_be_configured(self):
        conf_str = """
                    [Main]
                    name=bad module
                    exec_cmd=runit.sh
                    [Outputs]
                    output=/path/not/configured
                    # no inputs
                    """
        with self.assertLogs(level="ERROR") as logs:
            attempt_load(conf_str, self.db)
        all_logs = ' '.join(logs.output).lower()
        self.assertIn('configured', all_logs)

    def test_schema_name_must_be_valid(self):
        conf_str = """
                    [Main]
                    name=bad module
                    exec_cmd=runit.sh
                    #data is a reserved name
                    db_schema=data
                    [Outputs]
                    output=/path/to/output:float32[x]
                    # no inputs
                    """
        with self.assertLogs(level="ERROR") as logs:
            attempt_load(conf_str, self.db)
        all_logs = ' '.join(logs.output).lower()
        self.assertIn('schema', all_logs)


def attempt_load(conf_str, db: Session):
    with tempfile.TemporaryDirectory() as conf_dir:
        with open(os.path.join(conf_dir, "invalid.conf"), 'w') as f:
            f.write(conf_str)
        load_modules.run(conf_dir, db)
