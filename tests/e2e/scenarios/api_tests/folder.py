import unittest
from joule import api, errors


class TestFolderMethods(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self):
        self.node = api.get_node()
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
        stream = api.DataStream(name="s1a1", elements=[api.Element(name="e1")])
        await self.node.data_stream_create(stream, "/test/f1/f1a")
        stream.name = "s1a2"
        await self.node.data_stream_create(stream, "/test/f1/f1a")
        stream.name = "s1a"
        await self.node.data_stream_create(stream, "/test/f1")
        stream.name = "s2a1a"
        await self.node.data_stream_create(stream, "/test/f2/f2a")

    async def asyncTearDown(self):
        await self.node.folder_delete("/test", recursive=True)
        await self.node.close()

    async def test_folder_root(self):
        root = await self.node.folder_root()
        self.assertTrue(root.locked)
        self.assertEqual('root', root.name)
        # should have all of the streams and folders, check a few
        f_test = [f for f in root.children if f.name == 'test'][0]
        f1 = [f for f in f_test.children if f.name == 'f1'][0]
        s1a = [s for s in f1.data_streams if s.name == 's1a'][0]
        self.assertEqual("e1", s1a.elements[0].name)

    async def test_folder_move_to_existing_destination(self):
        await self.node.folder_move("/test/f1/f1a", "/test/f2")
        s1a1 = await self.node.data_stream_get("/test/f2/f1a/s1a1")
        self.assertEqual("s1a1", s1a1.name)

    async def test_folder_move_to_new_destination(self):
        await self.node.folder_move("/test/f1/f1a", "/test/new")
        s1a1 = await self.node.data_stream_get("/test/new/f1a/s1a1")
        self.assertEqual("s1a1", s1a1.name)

    async def test_folder_move_errors(self):
        # source does not exist
        with self.assertRaises(errors.ApiError):
            await self.node.folder_move("/test/f1/bad", "/test/f2")
        # circular graph
        with self.assertRaises(errors.ApiError):
            await self.node.folder_move("/test/f1", "/test/f1/f1a")
        # name conflict
        stream = api.DataStream(name="s1a1", elements=[api.Element(name="e1")])
        await self.node.data_stream_create(stream, "/test/f1/f2")
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

    async def test_folder_delete(self):
        s2a1a = await self.node.data_stream_get("/test/f2/f2a/s2a1a")
        await self.node.folder_delete("/test/f2/f2a")
        # folder is deleted
        f2 = await self.node.folder_get("/test/f2")
        self.assertEqual(0, len(f2.children))
        # streams in folder are deleted
        with self.assertRaises(errors.ApiError):
            await self.node.data_stream_get(s2a1a)

    async def test_folder_delete_errors(self):
        # folder does not exist
        with self.assertRaises(errors.ApiError):
            await self.node.folder_delete("/test/bad")
        # non-empty folder without recursive flag
        with self.assertRaises(errors.ApiError):
            await self.node.folder_delete("/test/f2")
        # locked folder
        with self.assertRaises(errors.ApiError):
            await self.node.folder_delete("/live")
        with self.assertRaises(errors.ApiError):
            await self.node.folder_delete("/archive")
        # all streams should still exist
        await self.node.data_stream_get("/live/base")
        await self.node.data_stream_get("/archive/data1")
        await self.node.data_stream_get("/test/f2/f2a/s2a1a")

