#!/usr/bin/python3
import time
import numpy as np
import asyncio
from joule.models.pipes import EmptyPipe
from joule import api


def main():
    time.sleep(8)  # wait for jouled to boot and collect data
    asyncio.run(_run())


async def _run():
    node = api.get_node()
    await check_modules(node)
    await check_logs(node)
    await check_data(node)
    await node.close()


async def check_modules(node: api.BaseNode):
    """
    Test: check module status
    Goal:
      normal1: running some nonzero memory
      normal2: running some nonzero memory
      cadder:  running some nonzero memory
      broken:  present (could be running or failed)
      misconfigured: not present b/c can't be loaded
    """
    modules = await node.module_list(statistics=True)
    assert (len(modules) == 4)  # normal1,normal2,filter,broken
    for module in modules:
        if module.name in ['Normal1', 'Normal2', 'CAdder']:
            if module.statistics.pid is None:
                logs = await node.module_logs(module.name)
                print(module.name)
                for line in logs:
                    print(line)

            assert module.statistics.pid is not None, module.name
        elif module.name == 'Broken':
            pass
        else:
            assert 0  # unexpected module in status report


async def check_data(node: api.BaseNode):
    """
    Test: check data inserted into nilmdb
    Goal:
      /bc/normal1/data is int32_1, has 1 interval with >500 samples
      /bc/normal2/subpath/data  is int32_1, >1 intervals each with 100 samples
      /bc/broken/data is float64_1, has separated intervals of data
      /bc/filter3/data is float64_1, has separated intervals of data
      both normal1 and normal2 have decimations
    """
    normal1_path = "/bc/normal1/data"
    normal2_path = "/bc/normal2/subpath/data"
    broken_path = "/bc/broken/data"
    filter1_path = "/bc/filter1/data"
    filter2_path = "/bc/filter2/data"
    for path in [normal1_path, normal2_path,
                 filter1_path, filter2_path,
                 broken_path]:
        # read 50 *live* samples from each stream
        pipe = await node.data_read(path)
        if 'broken' not in path:
            assert pipe.layout == "int32_1"
        else:
            assert pipe.layout == "float64_1"
        len_data = 0
        while not pipe.is_empty():
            data = await pipe.read()
            len_data += len(data)
            if len_data > 50:
                break
            pipe.consume(len(data))
        await pipe.close()

    # check intervals
    for path in [normal1_path, normal2_path,
                 filter1_path, filter2_path]:
        intervals = await node.data_intervals(path)
        assert len(intervals) == 1, 'path [%s] intervals %r' % (
            path, intervals)
    intervals = await node.data_intervals(broken_path)
    assert len(intervals) > 1, 'path [%s] intervals %r' % (
        broken_path, intervals)

    # read historic data to check if is correct

    # verify the filter module executed correctly
    # use the filter time bounds because to extract
    # the data to compare
    stream_info = await node.data_stream_info(filter1_path)
    p = await node.data_read(normal1_path,
                             start=stream_info.start,
                             end=stream_info.end,
                             max_rows=50)
    expected_data = await p.read(True)
    assert 0 < len(expected_data) <= 50
    expected_data[:, 1:] += 10.0
    await p.close()
    p = await node.data_read(filter1_path,
                             start=stream_info.start,
                             end=stream_info.end,
                             max_rows=50)
    actual_data = await p.read(True)
    verify_len = min(len(actual_data), len(expected_data))
    np.testing.assert_almost_equal(actual_data[:verify_len, :],
                                   expected_data[:verify_len, :])

    stream_info = await node.data_stream_info(filter2_path)
    p = await node.data_read(normal2_path,
                             start=stream_info.start,
                             end=stream_info.end,
                             max_rows=100)
    expected_data = await p.read(True)
    assert 0 < len(expected_data) <= 100
    expected_data[:, 1:] += 11.0
    await p.close()
    p = await node.data_read(filter2_path,
                             start=stream_info.start,
                             end=stream_info.end,
                             max_rows=100)
    actual_data = await p.read(True)
    verify_len = min(len(actual_data), len(expected_data))
    np.testing.assert_almost_equal(actual_data[:verify_len, :],
                                   expected_data[:verify_len, :])


async def check_logs(node: api.BaseNode):
    """
    Test: logs should contain info and stderr from modules
    Goal: 
      Normal1: says "starting" somewhere once
      Normal2: says "starting" somewhere once
      Filter: says "starting" somewhere once
      Broken: says "starting" and more than one "restarting"
      Misconfigured: no logs
    """
    for module_name in ["Normal1", "Normal2", "CAdder", "Broken"]:
        logs = await node.module_logs(module_name)
        num_starts = 0
        for line in logs:
            if "---starting module---" in line:
                num_starts += 1
        if module_name != 'Broken':
            assert num_starts == 1
        else:
            assert num_starts > 1


if __name__ == "__main__":
    main()
    print("OK")
