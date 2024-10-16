#!/usr/bin/env python3
import time
import asyncio

from joule import api

async def _run():
    node = api.get_node()
    

if __name__ == "__main__":
    time.sleep(1)  # wait for jouled to boot
    asyncio.run(_run())