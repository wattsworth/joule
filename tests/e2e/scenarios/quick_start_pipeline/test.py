#!/usr/bin/env python3
import time
import socket
import subprocess
import os
import asyncio
import aiohttp
from joule import api
from joule.api.data_stream import DataStream, Element
import unittest

test_case = unittest.TestCase()

async def main():
    time.sleep(4)  # wait for jouled to boot and modules to start
    # start a standalone visualizer module with mock data
    module_config = os.path.join(os.path.dirname(__file__), "standalone_app.conf")
    app_port = _find_port()
    standalone_app= subprocess.Popen(
        f"coverage run --rcfile=/joule/.coveragerc -m joule.client.builtins.visualizer --module_config={module_config} --live --port={app_port}".split(" "))
    time.sleep(4)  # let the module start
    await validate_operation(standalone_app, app_port)
    standalone_app.kill()

async def validate_operation(standalone_app, app_port):
    # get the node
    node = api.get_node()
    integrated_app = await node.module_get("Data App")

    async with aiohttp.ClientSession() as session:
        # the title from the module configuration file should be on the page
        async with session.get(f"http://localhost:{app_port}") as response:
            html = await response.text()
            test_case.assertIn("Standalone App", html)

        # cannot get the integrated module without permission
        async with session.get(f"http://localhost/joule/app/m{integrated_app.id}/") as response:
            test_case.assertEqual(response.status, 403)
            
        # can get the integrated module with permission, title should be on the page
        async with session.get(f"http://localhost/joule/app/m{integrated_app.id}/", headers={"X-API-KEY": node._key}) as response:
            test_case.assertEqual(response.status, 200)
            html = await response.text()
            test_case.assertIn("Quick Start Data Pipeline", html)

        # resetting the module should clear the min/max ranges
        async with session.get(f"http://localhost:{app_port}/data.json") as response:
            test_case.assertEqual(response.status, 200)
            data = await response.json()
            for element in data:
                test_case.assertLessEqual(element["min"], element["value"])
                test_case.assertGreaterEqual(element["max"], element["value"])

        async with session.post(f"http://localhost:{app_port}/reset.json") as response:
            test_case.assertEqual(response.status, 200)

        async with session.get(f"http://localhost:{app_port}/data.json") as response:
            test_case.assertEqual(response.status, 200)
            data = await response.json()
            for element in data:
                test_case.assertEqual(element["min"], "&mdash;")
                test_case.assertEqual(element["max"], "&mdash;")
           

    await node.close()
    
def _find_port():
    # return an available TCP port, check to make sure it is available
    # before returning
    for port in range(8000, 9000):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            try:
                sock.bind(('localhost', port))
                return port
            except OSError:
                continue


if __name__ == "__main__":
    asyncio.run(main())
    print("OK")