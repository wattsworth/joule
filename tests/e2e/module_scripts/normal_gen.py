#!/usr/bin/env python3

import joule
import joule.utilities
import numpy as np
import asyncio

rows = 100
freq = 40  # Hz


class NormalGen(joule.ReaderModule):

    async def run(self, parsed_args, output):
            data = 100 * np.sin(np.arange(0, 2 * np.pi, 2 * np.pi / rows))
            data.shape = (rows, 1)
            ts_inc = 1 / rows * (1 / freq) * 1e6  # microseconds
            data_ts = joule.utilities.time_now()
            while not self.stop_requested:
                top_ts = data_ts + 100 * ts_inc
                ts = np.array(np.linspace(data_ts, top_ts, rows,
                                          endpoint=False), dtype=np.uint64)
                ts.shape = (rows, 1)
                ts_data = np.hstack((ts, data))
                await output.write(ts_data)
                data_ts = top_ts
                await asyncio.sleep(rows / freq)


if __name__ == "__main__":
    r = NormalGen()
    r.start()
