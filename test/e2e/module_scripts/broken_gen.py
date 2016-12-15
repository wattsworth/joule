#!/usr/bin/python3

from joule.utils.time import now as time_now
import joule.utils.client
import time
import numpy as np
import sys
import argparse
import asyncio

rows = 100
freq = 4  # Hz

"""
Inserts 100 samples and then fails with an exception
"""


async def main(ts, pipe):
    data = np.sin(np.arange(0, 2 * np.pi, 2 * np.pi / rows))
    data.shape = (rows, 1)
    ts_inc = 1 / rows * (1 / freq) * 1e6  # microseconds
    data_ts = ts
    while(True):
        top_ts = data_ts + 100 * ts_inc
        ts = np.array(np.linspace(data_ts, top_ts, rows,
                                  endpoint=False), dtype=np.uint64)
        ts.shape = (rows, 1)
        ts_data = np.hstack((ts, data))
        await pipe.write(ts_data)
        #print("[%d-%d]" % (data_ts, ts[-1]), file=sys.stderr)
        #sys.stderr.flush()
        data_ts = top_ts
        time.sleep(1 / freq)
        raise ValueError

if __name__ == "__main__":
    print("starting!")
    parser = argparse.ArgumentParser()
    joule.utils.client.add_args(parser)
    args = parser.parse_args()
    (_,pipes_out)=joule.utils.client.build_pipes(args)
    my_pipe = pipes_out['path1']
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main(time_now(), my_pipe))
    loop.close()

