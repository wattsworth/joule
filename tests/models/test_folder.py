import unittest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from joule.services import parse_pipe_config
from joule.models import Stream, Base, folder, Folder


class TestFolder(unittest.TestCase):

    def setUp(self):
        # create a database
        engine = create_engine('sqlite://')
        Base.metadata.create_all(engine)
        self.db = Session(bind=engine)

    def test_get_stream_path(self):
        # create a stream and then find it again
        stream = parse_pipe_config.run("/very/long/path/to/stream:float32[x]", self.db)
        path = folder.get_stream_path(stream)
        self.assertEqual("/very/long/path/to/stream", path)

        # stream outside the database has no path
        stream = Stream(name="all alone")
        self.assertIsNone(folder.get_stream_path(stream))

    def test_find_or_create(self):
        my_folder = folder.find_or_create("/new/folder/path", self.db)
        self.assertEqual(self.db.query(Folder).count(), 4)
        # trailing slash is ignored
        same_folder = folder.find_or_create("/new/folder/path/", self.db)
        self.assertEqual(self.db.query(Folder).count(), 4)
        self.assertEqual(my_folder, same_folder)
