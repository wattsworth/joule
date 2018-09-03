from sqlalchemy import create_engine
from sqlalchemy.orm import Session
import unittest
from joule.models import Base
from joule.errors import ConfigurationError
from joule.services import parse_pipe_config


class TestParsePipeConfigErrors(unittest.TestCase):

    def setUp(self):
        # create a database
        engine = create_engine('sqlite://')
        Base.metadata.create_all(engine)
        self.db = Session(bind=engine)

    def test_ensures_valid_path_and_name(self):
        bad_configs = [
            "/no_path:int8[x,y]",
            "missing/slash:int8[x,y]",
            "justbad",
            "",
            "/tooshort"
            "/no/data/format",
            "/empty/format:[]",
            "/inval:d/characters",
            "/bad/elements:bad[x,y]",
            "/bad/elements:float32[x,",
            "/bad/elements:float32[x,y",
            "/bad/elements:float32[,",
            "//too/many//slashes",
            "remote.stream/without/space"
            "remote:3000 /no/inline_config"
        ]
        for config in bad_configs:
            with self.assertRaises(ConfigurationError):
                parse_pipe_config.run(config, self.db)
