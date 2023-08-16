import unittest
from joule import api, errors


class TestStreamMethods(unittest.IsolatedAsyncioTestCase):

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

    async def test_stream_move_to_existing_folder(self):
        await self.node.data_stream_move("/test/f1/f1a/s1a1", "/test/f2/f2a")
        stream = await self.node.data_stream_get("/test/f2/f2a/s1a1")
        self.assertEqual("s1a1", stream.name)

    async def test_stream_move_to_new_folder(self):
        await self.node.data_stream_move("/test/f1/f1a/s1a1", "/test/f2/new")
        stream = await self.node.data_stream_get("/test/f2/new/s1a1")
        self.assertEqual("s1a1", stream.name)

    async def test_move_errors(self):
        # stream does not exist
        with self.assertRaises(errors.ApiError):
            await self.node.data_stream_move("/test/f1/f1a/bad", "/test/f2/new")

        # name conflict
        stream = api.DataStream(name="s1a1", elements=[api.Element(name="e1")])
        await self.node.data_stream_create(stream, "/test/f2")

        with self.assertRaises(errors.ApiError):
            await self.node.data_stream_move(stream, "/test/f1/f1a")

        # locked stream
        with self.assertRaises(errors.ApiError):
            await self.node.data_stream_move("/live/base", "/test/f2/new")

    async def test_stream_update(self):
        stream = await self.node.data_stream_get("/test/f1/f1a/s1a1")
        stream.name = "new name"
        stream.description = "new description"
        stream.elements[0].name = "new element name"
        await self.node.data_stream_update(stream)
        stream = await self.node.data_stream_get(stream)
        self.assertEqual(stream.name, "new name")
        self.assertEqual(stream.description, "new description")
        self.assertEqual(stream.elements[0].name, "new element name")

    async def testStreamUpdateErrors(self):
        # locked stream
        stream = await self.node.data_stream_get("/live/base")
        with self.assertRaises(errors.ApiError):
            stream.name = "invalid"
            await self.node.data_stream_update(stream)

        # cannot change number of elements
        stream = await self.node.data_stream_get("/test/f1/f1a/s1a1")
        with self.assertRaises(errors.ApiError):
            stream.elements.append(api.Element(name="invalid"))
            await self.node.data_stream_update(stream)

        # name conflict
        stream = await self.node.data_stream_get("/test/f1/f1a/s1a1")
        with self.assertRaises(errors.ApiError):
            stream.name = "s1a2"
            await self.node.data_stream_update(stream)

    async def testStreamCreate(self):
        # this is done in the setUp calls already
        pass

    async def testStreamCreateErrors(self):
        # name conflict
        stream = api.DataStream(name="s1a1", elements=[api.Element(name="e1")])
        with self.assertRaises(errors.ApiError):
            await self.node.data_stream_create(stream, "/test/f1/f1a")

        # missing elements
        stream = api.DataStream(name="no elements", elements=[])
        with self.assertRaises(errors.ApiError):
            await self.node.data_stream_create(stream, "/test/f1/f1a")

        # invalid values
        stream = api.DataStream(name="invalid datatype", datatype="invalid",
                                elements=[api.Element(name="e1")])
        with self.assertRaises(errors.ApiError):
            await self.node.data_stream_create(stream, "/test/f1/f1a")

    async def testStreamDelete(self):
        await self.node.data_stream_delete("/test/f1/f1a/s1a1")
        with self.assertRaises(errors.ApiError):
            await self.node.data_stream_get("/test/f1/f1a/s1a1")

    async def testStreamDeleteErrors(self):
        # missing stream
        with self.assertRaises(errors.ApiError):
            await self.node.data_stream_delete("/test/f1/f1a/bad")

        # locked stream
        with self.assertRaises(errors.ApiError):
            await self.node.data_stream_delete("/live/plus1")
        stream = await self.node.data_stream_get("/live/plus1")
        self.assertEqual(stream.name, "plus1")

    async def testStreamInfo(self):
        info = await self.node.data_stream_info("/live/base")
        self.assertGreater(info.total_time, 0)

        info = await self.node.data_stream_info("/archive/data2")
        self.assertEqual(info.total_time, 0)

    async def testStreamInfoErrors(self):
        # missing stream
        with self.assertRaises(errors.ApiError):
            await self.node.data_stream_info("/test/bad")
