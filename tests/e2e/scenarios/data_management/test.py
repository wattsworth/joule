#!/usr/bin/env python3
import time
import asyncio
import numpy as np
from joule import api
from joule.utilities import human_to_timestamp as h2ts
from click.testing import CliRunner
import unittest
from joule.cli import main

t1 = h2ts('1 Sep 2020 00:00:00')
t2 = h2ts('2 Sep 2020 00:00:00')
t3 = h2ts('3 Sep 2020 00:00:00')
t4 = h2ts('4 Sep 2020 00:00:00')
t5 = h2ts('5 Sep 2020 00:00:00')
t6 = h2ts('6 Sep 2020 00:00:00')
t7 = h2ts('7 Sep 2020 00:00:00')
t8 = h2ts('8 Sep 2020 00:00:00')
t9 = h2ts('9 Sep 2020 00:00:00')
tA = h2ts('10 Sep 2020 00:00:00')
tB = h2ts('11 Sep 2020 00:00:00')
tC = h2ts('12 Sep 2020 00:00:00')
tD = h2ts('13 Sep 2020 00:00:00')
tE = h2ts('14 Sep 2020 00:00:00')

test_case = unittest.TestCase()

async def setup():
    node = api.get_node()
    print("loading test data...")
    # put sample data into /original/stream1 and /original/stream2, both have 5 elements
    #
    # times:    1  2    3 4  5 6  7 8  9 A                      B  C  D       E
    # stream1:  |-------| |-------| |------------------------------|
    # stream2:     |---------| |-------| |----------------------|     |-------|
    # =========
    # expected:    |----| |--| |--| |--| |----------------------|   
    #              2    3 4  5 6  7 8  9 A                      B
    # Make all the time stamps 1 day apart


    # create the streams
    stream1 = api.DataStream("stream1", elements=[api.Element(name=f"elem1_{i}") for i in range(5)])
    stream1 = await node.data_stream_create(stream1,"/original")
    pipe = await node.data_write(stream1)
    await pipe.write(_create_data(t1, t3))
    await pipe.write(_create_data(t4, t7))
    await pipe.write(_create_data(t8, tC))
    await pipe.write(_create_data(tD, tE))
    await pipe.close()

    stream2 = api.DataStream("stream2", elements=[api.Element(name=f"elem2_{i}") for i in range(5)])
    stream2 = await node.data_stream_create(stream2,"/original")
    pipe = await node.data_write(stream2)
    await pipe.write(_create_data(t2, t5))
    await pipe.write(_create_data(t6, t9))
    await pipe.write(_create_data(tA, tB))
    await pipe.close()
    await node.close()
    
def _create_data(start, end):
    num_points = int((end - start)//1e6)
    step = 1e6
    """Create a random block of data with [layout] structure"""
    ts = np.arange(start, start + step * num_points, step, dtype=np.uint64)
    sarray = np.zeros(len(ts), dtype=np.dtype([('timestamp', '<i8'), ('data', '<f4', (5,))]))
    data = np.random.rand(num_points, 5)
    sarray['timestamp'] = ts
    sarray['data'] = data
    return sarray

def _assert_success(result):
    if result.exit_code != 0:
        print("output: ", result.output)
        print("exception: ", result.exception)
    test_case.assertEqual(result.exit_code, 0)

def backup_data():
    runner = CliRunner()
    result = runner.invoke(main, "data read /original/stream1 --file /tmp/stream1.h5".split(" "))
    _assert_success(result)
    result = runner.invoke(main, "data ingest /tmp/stream1.h5 --stream /ingested/stream1".split(" "))
    _assert_success(result)
    result = runner.invoke(main, "stream info /ingested/stream1".split(" "))
    _assert_success(result)
    print(result.output)
    assert result.exit_code == 0

def process_data():
    print("running filters...")
    runner = CliRunner()
    result = runner.invoke(main, "data merge -p /original/stream1 -s /original/stream2 -d /filtered/merge1_2".split(" "), input="Y\n")
    _assert_success(result)
    result = runner.invoke(main, "data filter median -w 3 /original/stream2 /filtered/median2".split(" "), input="Y\n")
    _assert_success(result)
    result = runner.invoke(main, "data filter mean -w 3 /original/stream1 /filtered/mean1".split(" "), input="Y\n")
    _assert_success(result)

if __name__ == "__main__":
    time.sleep(8)  # wait for jouled to boot
    asyncio.run(setup())
    process_data()
    backup_data()

