#!/usr/bin/env python3
import time
import re
import subprocess
import numpy as np
import asyncio

from joule import api
from joule.api.data_stream import DataStream, Element
from joule.models.pipes import EmptyPipe

NILMDB_URL = "http://nilmdb"


def main():
    time.sleep(1)  # wait for jouled to boot
    asyncio.run(_run())


async def _run():
    node = api.get_node()
    procs = start_standalone_procs1()

    time.sleep(4)  # let procs run
    stop_standalone_procs(procs)

    time.sleep(8)  # close sockets
    procs = await start_standalone_procs2(node)
    time.sleep(4)  # let procs run
    stop_standalone_procs(procs)
    time.sleep(4)  # close sockets

    await check_streams(node)
    await check_modules(node)
    await check_data(node)
    await check_logs(node)
    await node.close()
    return


def start_standalone_procs1():
    # proc1 reads /counting/base and writes to /counting/plus3
    p1 = subprocess.Popen(build_standalone_args("proc1"))
    time.sleep(1)

    # proc1a reads /counting/base and writes to /counting/plus3
    #   fails because proc1 is already writing to path
    p1a = subprocess.run(build_standalone_args("proc1"),
                         stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE,
                         universal_newlines=True)
    assert p1a.stderr.find("plus3") != -1
    # proc2 tries to read from /bad/path but fails
    p2 = subprocess.run(build_standalone_args("proc2"),
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        universal_newlines=True)
    assert p2.stderr.find("not being produced") != -1
    return [p1]


async def start_standalone_procs2(node: api.BaseNode):
    # proc3 tries to write to /counting/plus3 with wrong dtype
    p3 = subprocess.run(build_standalone_args("proc3"),
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        universal_newlines=True,
                        timeout=3)
    assert p3.stderr.find("layout") != -1

    #  proc4 reads /counting/base and writes to /counting/plus3
    p1 = subprocess.Popen(build_standalone_args("proc1"))

    stream = DataStream()
    stream.name = "int8"
    stream.datatype = "int8"
    for x in range(3):
        e = Element()
        e.name = 'item%d' % x
        e.index = x
        stream.elements.append(e)
    await node.data_stream_create(stream, "/exists")

    # proc5 tries to write to /exists/int8 with wrong element count
    p4 = subprocess.run(build_standalone_args("proc4"),
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        universal_newlines=True)
    assert p4.stderr.find("layout") != -1

    return [p1]


def build_standalone_args(proc_dir):
    scenario_dir = "/joule/tests/e2e/scenarios/standalone_modules/"
    base_dir = scenario_dir + "standalone_modules/" + proc_dir + "/"
    return ["/joule/tests/e2e/module_scripts/adder.py",
            "3", "--live",
            "--module_config", base_dir + "module.conf",
            "--stream_configs", base_dir + "stream_configs"]


def stop_standalone_procs(procs):
    for proc in procs:
        proc.kill()


async def check_modules(node: api.BaseNode):
    """
    Test: check module status
    Goal:
      counter: running some nonzero memory
      plus1: running some nonzero memory
    """
    modules = await node.module_list()
    assert (len(modules) == 2)


async def check_streams(node: api.BaseNode):
    """
    Test: check streams created by standalone modules
    Goal:
        /counting/plus3 should have customized display_type and keep settings
    """
    plus3 = await node.data_stream_get("/counting/plus3")
    assert (plus3.keep_us == (5 * 24 * 60 * 60 * 1e6))  # keep=5d
    assert (plus3.elements[0].display_type == "DISCRETE")


async def check_data(node: api.BaseNode):
    """
    Test: check data inserted into nilmdb
    Goal:
      /counting/base is int32_1, 1 interval with >300 samples
      /counting/plus1 is int32_1, data is base+1
      /counting/plus3 is int32_1, data is base+3

      all paths have decimations
    """
    base_path = "/counting/base"
    plus1_path = "/counting/plus1"
    plus3_path = "/counting/plus3"
    for path in [base_path, plus1_path]:
        # read 50 *live* samples from each stream
        pipe = await node.data_read(path)
        assert pipe.layout == "int32_1"
        num_intervals = 1
        len_data = 0
        while True:
            try:
                data = await pipe.read()
                len_data += len(data)
                if len_data > 50:
                    break
            except EmptyPipe:
                break
            if pipe.end_of_interval:
                num_intervals += 1
            pipe.consume(len(data))

        # streams should have single continuous interval
        assert num_intervals == 1, "%s has %d intervals" % (path, num_intervals)
        assert len_data > 50
        await pipe.close()

    # verify plus3_path has 2 intervals
    intervals = await node.data_intervals(plus3_path)
    assert len(intervals) == 2, intervals

    # verify the filter module executed correctly
    # use the filter time bounds because to extract
    # the data to compare
    stream_info = await node.data_stream_info(plus1_path)
    p = await node.data_read(base_path,
                             start=stream_info.start,
                             end=stream_info.end,
                             max_rows=50)
    expected_data = await p.read(True)
    assert 0 < len(expected_data) <= 50
    expected_data[:, 1:] += 1
    await p.close()
    p = await node.data_read(plus1_path,
                             start=stream_info.start,
                             end=stream_info.end,
                             max_rows=50)
    actual_data = await p.read(True)
    verify_len = min(len(actual_data), len(expected_data))
    np.testing.assert_almost_equal(actual_data[:verify_len, :],
                                   expected_data[:verify_len, :])


async def check_logs(node: api.BaseNode):
    """
    Test: logs should contain info and stderr from modules
    Goal: 
      counter: says "starting" somewhere once
      plus1: says "starting" somewhere once
    """
    for module_name in ["counter", "plus1"]:
        logs = await node.module_logs(module_name)
        num_starts = len(re.findall("---starting module---", ' '.join(logs)))
        assert (num_starts == 1)


if __name__ == "__main__":
    main()
    print("OK")
