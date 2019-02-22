import unittest
import asynctest
from joule import api, errors


class TestFolderMethods(asynctest.TestCase):

    async def setUp(self):
        self.node = api.Node()
        """
        └── test
            ├── f1
            │   ├── f1a
            │   │   ├── s1a1
            │   │   └── s1a2
            │   └── s1a
            └── f2
                └── f2a
                    └── s2a1a
        """
        # remove contents of test directory
        try:
            await self.node.folder_delete("/test", recursive=True)
        except errors.ApiError:
            pass

        stream = api.Stream(name="s1a1", elements=[api.Element(name="e1")])
        await self.node.stream_create(stream, "/test/f1/f1a")
        stream.name = "s1a2"
        await self.node.stream_create(stream, "/test/f1/f1a")
        stream.name = "s1a"
        await self.node.stream_create(stream, "/test/f1")
        stream.name = "s2a1a"
        await self.node.stream_create(stream, "/test/f2/f2a")

    async def tearDown(self):
        await self.node.close()

    async def test_folder_root(self):
        root = await self.node.folder_root()
        self.assertTrue(root.locked)
        self.assertEqual('root', root.name)
        # should have all of the streams and folders, check a few
        f_test = [f for f in root.children if f.name == 'test'][0]
        f1 = [f for f in f_test.children if f.name == 'f1'][0]
        s1a = [s for s in f1.streams if s.name == 's1a'][0]
        self.assertEqual("e1", s1a.elements[0].name)

    async def test_folder_move_to_existing_destination(self):
        await self.node.folder_move("/test/f1/f1a", "/test/f2")
        s1a1 = await self.node.stream_get("/test/f2/f1a/s1a1")
        self.assertEqual("s1a1", s1a1.name)

    async def test_folder_move_to_new_destination(self):
        await self.node.folder_move("/test/f1/f1a", "/test/new")
        s1a1 = await self.node.stream_get("/test/new/f1a/s1a1")
        self.assertEqual("s1a1", s1a1.name)

    async def test_folder_move_errors(self):
        # source does not exist
        with self.assertRaises(errors.ApiError):
            await self.node.folder_move("/test/f1/bad", "/test/f2")
        # circular graph
        with self.assertRaises(errors.ApiError):
            await self.node.folder_move("/test/f1", "/test/f1/f1a")
        # name conflict
        stream = api.Stream(name="s1a1", elements=[api.Element(name="e1")])
        await self.node.stream_create(stream, "/test/f1/f2")
        with self.assertRaises(errors.ApiError):
            await self.node.folder_move("/test/f1/f2", "/test")
        # locked folder
        with self.assertRaises(errors.ApiError):
            await self.node.folder_move("/live/base", "/test")

    async def test_folder_update(self):
        f1 = await self.node.folder_get("/test/f1")
        f1.name = "f1_new"
        f1.description = "new description"
        await self.node.folder_update(f1)
        f1_new = await self.node.folder_get(f1.id)
        self.assertEqual(f1_new.name, "f1_new")
        self.assertEqual(f1_new.description, "new description")

    async def test_folder_update_errors(self):
        # name cannot be blank
        f1 = await self.node.folder_get("/test/f1")
        f1.name = ""
        with self.assertRaises(errors.ApiError):
            await self.node.folder_update(f1)
        f1.name = None
        with self.assertRaises(errors.ApiError):
            await self.node.folder_update(f1)
        # name cannot conflict with a peer
        f1.name = "f2"
        with self.assertRaises(errors.ApiError):
            await self.node.folder_update(f1)
        # make sure name didn't change
        f1 = await self.node.folder_get(f1.id)
        self.assertEqual("f1", f1.name)
