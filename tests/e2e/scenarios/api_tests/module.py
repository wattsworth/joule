import unittest

from joule import api, errors


class TestModuleMethods(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self):
        self.node = api.get_node()

    async def asyncTearDown(self) -> None:
        await self.node.close()

    async def test_module_get(self):
        module = await self.node.module_get("plus1")
        output_path = module.outputs['output']
        input_path = module.inputs['input']
        self.assertEqual(output_path, '/live/plus1')
        self.assertEqual(input_path, '/live/base')

    async def test_module_get_errors(self):
        with self.assertRaises(errors.ApiError):
            await self.node.module_get("bad")

    async def test_module_list(self):
        modules = await self.node.module_list()
        self.assertEqual(len(modules),2)
        for m in modules:
            self.assertTrue(type(m) is api.Module)

    async def test_module_logs(self):
        logs = await self.node.module_logs("plus1")
        self.assertIn("starting", logs[0])

    async def test_module_logs_errors(self):
        with self.assertRaises(errors.ApiError):
            await self.node.module_logs("bad")
