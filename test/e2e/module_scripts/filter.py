#!/usr/bin/python3
"""
InStream1 ==> x2 ==> InStream2
InStream2 ==> x3 ==> OutStream2
"""

import asyncio
import argparse
import joule.utils.client
import sys


async def echo_pipe(np_in, np_out, factor=1.0):
    while(True):
        data = await np_in.read(flatten=True)
        np_in.consume(len(data))
        data[:, 1:] *= factor
        await np_out.write(data)

if __name__ == "__main__":
    sys.stderr.write("starting filter!\n")
    sys.stderr.flush()
    parser = argparse.ArgumentParser("demo")
    joule.utils.client.add_args(parser)
    args = parser.parse_args()

    (pipes_in, pipes_out) = joule.utils.client.build_pipes(args)

    np_in1 = pipes_in['path1']
    np_in2 = pipes_in['path2']
    np_in3 = pipes_in['path3']
    np_out1 = pipes_out['path1']
    np_out2 = pipes_out['path2']
    np_out3 = pipes_out['path3']

    tasks = [
        asyncio.ensure_future(echo_pipe(np_in1, np_out1, factor=2)),
        asyncio.ensure_future(echo_pipe(np_in2, np_out2, factor=3)),
        asyncio.ensure_future(echo_pipe(np_in3, np_out3, factor=4))]

    loop = asyncio.get_event_loop()
    loop.run_until_complete(asyncio.gather(*tasks))
    loop.close()
    
    print("all done")
