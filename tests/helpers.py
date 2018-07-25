import numpy as np
import configparser
import asyncio
import unittest


def create_data(layout:str,
                length=100,
                step=1000,  # in us
                start=1476152086000000):  # 10 Oct 2016 10:15PM
    """Create a random block of NilmDB data with [layout] structure"""
    ts = np.arange(start, start + step * length, step, dtype=np.uint64)

    # Convert to structured array
    (ltype, lcount, dtype) = parse_layout(layout)
    sarray = np.zeros(len(ts), dtype=dtype)
    if "float" in ltype:
        data = np.random.rand(length, lcount)
    elif "uint" in ltype:
        data = np.random.randint(0, high=100, size=(
            length, lcount), dtype=dtype[1].base)
    else:
        data = np.random.randint(-50, high=50,
                                 size=(length, lcount), dtype=dtype[1].base)

    sarray['timestamp'] = ts
    # Need the squeeze in case sarray['data'] is 1 dimensional
    sarray['data'] = np.squeeze(data)
    return sarray


def to_chunks(data, chunk_size):
    """Yield successive MAX_BLOCK_SIZE chunks of data."""
    for i in range(0, len(data), chunk_size):
        yield data[i:i + chunk_size]


def parse_layout(layout):
    ltype = layout.split('_')[0]
    lcount = int(layout.split('_')[1])
    if ltype.startswith('int'):
        atype = '<i' + str(int(ltype[3:]) // 8)
    elif ltype.startswith('uint'):
        atype = '<u' + str(int(ltype[4:]) // 8)
    elif ltype.startswith('float'):
        atype = '<f' + str(int(ltype[5:]) // 8)
    else:
        raise ValueError("bad layout")
    dtype = np.dtype([('timestamp', '<i8'), ('data', atype, lcount)])
    return ltype, lcount, dtype


def parse_configs(config_str):
    config = configparser.ConfigParser()
    config.read_string(config_str)
    return config


def mock_stream_info(streams):
    """pass in array of stream_info's:
       [['/test/path','float32_3'],
       ['/test/path2','float32_5'],...]
       returns a function to mock stream_info as a side_effect"""

    def stream_info(path):
        for stream in streams:
            if stream[0] == path:
                return [stream]
        return []
    return stream_info


class AsyncTestCase(unittest.TestCase):

    def setUp(self):
        self.loop = asyncio.new_event_loop()
        self.loop.set_debug(True)
        asyncio.set_event_loop(self.loop)

    def tearDown(self):
        closed = self.loop.is_closed()
        if not closed:
            self.loop.call_soon(self.loop.stop)
            self.loop.run_forever()
            self.loop.close()
        asyncio.set_event_loop(None)