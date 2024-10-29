#!/usr/bin/env python3
import time
import asyncio
import numpy as np
from joule import api
from joule import errors
from joule.utilities import human_to_timestamp as h2ts
from joule.utilities import timestamp_to_human as ts2h
from click.testing import CliRunner
from joule.constants import ApiErrorMessages
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
    node:api.BaseNode = api.get_node()
    print("loading test data...", end="")
    # put sample data into /original/stream1 and /original/stream2, both have 5 elements
    #
    # times:    1  2    3 4  5 6  7 8  9 A                      B  C  D       E
    # stream1:  |-------| |-------| |------------------------------|
    # stream2:     |---------| |-------| |----------------------|     |-------|
    # =========
    # expected:    |----| |--| |--| |--| |----------------------|   
    #              2    3 4  5 6  7 8  9 A                      B
    # Make all the time stamps 1 day apart


    # create the data streams
    stream1 = api.DataStream("stream1", elements=[api.Element(name=f"elem1_{i}") for i in range(5)])
    stream1 = await node.data_stream_create(stream1,"/original")
    pipe = await node.data_write(stream1)
    await pipe.write(_create_data(t1, t3))
    await pipe.close_interval()
    await pipe.write(_create_data(t4, t7))
    await pipe.close_interval()
    await pipe.write(_create_data(t8, tC))
    await pipe.close()

    stream2 = api.DataStream("stream2", elements=[api.Element(name=f"elem2_{i}") for i in range(5)])
    stream2 = await node.data_stream_create(stream2,"/original")
    pipe = await node.data_write(stream2)
    await pipe.write(_create_data(t2, t5))
    await pipe.close_interval()
    await pipe.write(_create_data(t6, t9))
    await pipe.close_interval()
    await pipe.write(_create_data(tA, tB))
    await pipe.close_interval()
    await pipe.write(_create_data(tD, tE))
    await pipe.close()

    # add annotations to the streams
    await node.annotation_create(api.Annotation(title="note",start=t1,end=t3,content="api annotation"), "/original/stream1")
    await node.annotation_create(api.Annotation(title="note2",start=t9,end=tA,content="api annotation"), "/original/stream2")

    # create the event streams
    events = []
    for ts in [t1, t2, t3, t4, t5, t6, t7, t8, t9, tA, tB, tC, tD, tE]:
        events.append(api.Event(start_time=ts,end_time=ts+60e6, content={"name": ts2h(ts)}))
    event_stream = await node.event_stream_create(api.EventStream(name="events",event_fields={"name": "string"}), "/original")
    await node.event_stream_write(event_stream, events)
    await node.close()
    print("OK")

def test_backup_data():
    runner = CliRunner()
    result = runner.invoke(main, "data read /original/stream1 --file /tmp/stream1.h5".split(" "))
    _assert_success(result)
    result = runner.invoke(main, "data ingest /tmp/stream1.h5 --stream /ingested/stream1".split(" "))
    _assert_success(result)
    async def _validate():
        node = api.get_node()
        orig_info = await node.data_stream_info("/original/stream1")
        new_info = await node.data_stream_info("/ingested/stream1")
        # all data should be copied over
        test_case.assertEqual(orig_info.start, new_info.start)
        test_case.assertEqual(orig_info.end, new_info.end)
        # just check to make sure the original stream has the expected data
        test_case.assertAlmostEqual(orig_info.start, t1, delta=10e6)
        test_case.assertAlmostEqual(orig_info.end, tC, delta=10e6)
        print(await node.data_intervals("/original/stream1"))
        print(await node.data_intervals("/ingested/stream1"))
        await node.close()
    asyncio.run(_validate())
    assert result.exit_code == 0

def test_process_data():
    print("running filters...")
    runner = CliRunner()
    result = runner.invoke(main, "data merge -p /original/stream1 -s /original/stream2 -d /filtered/merge1_2".split(" "), input="Y\n")
    _assert_success(result)
    result = runner.invoke(main, "data filter median -w 3 /original/stream2 /filtered/median2".split(" "), input="Y\n")
    _assert_success(result)
    result = runner.invoke(main, "data filter mean -w 3 /original/stream1 /filtered/mean1".split(" "), input="Y\n")
    _assert_success(result)

    ## run time bounded filters
    # times:    1  2    3 4  5 6  7 8  9 A                      B  C  D       E
    # stream1:  |-------| |-------| |------------------------------|
    # stream2:     |---------| |-------| |----------------------|     |-------|
    # =========
    # merge1_2:    |----| |--| |--| |--| |----------------------|        
    # median2b:           |--| |-------| |----|
    #                                         ^--A_2
    tA_2 = tA+2*60*60e6 # 2 hours after tA
    result = runner.invoke(main, f"data filter median -w 3 --start {t4} --end {tA_2} /original/stream2 /filtered/median2b".split(" "), input="Y\n")
    _assert_success(result)
  
    async def _validate():
        node = api.get_node()
        #await print_intervals(node,"/original/stream1")
        #await print_intervals(node,"/original/stream2")
        #await print_intervals(node,"/filtered/median2b")
        #await print_intervals(node,"/filtered/merge1_2")
        # should be within 10 seconds of the time bounds (depends on the sample generation by create_data)
        await assert_has_intervals(node, "/filtered/median2b", [(t4,t5),(t6,t9),(tA,tA_2)])
        await assert_has_intervals(node, "/filtered/merge1_2", [(t2,t3),(t4,t5),(t6,t7),(t8,t9),(tA,tB)])
        await node.close()
    
    asyncio.run(_validate())

def test_copy_all_data():
    print("copying all data...", end="")
    runner = CliRunner()
    result = runner.invoke(main, "folder copy /original /copy".split(" "), input="Y\n")
    _assert_success(result)
    async def _validate():
        node = api.get_node()
        orig_info = await node.data_stream_info("/original/stream1")
        copied_info = await node.data_stream_info("/copy/stream1")
        # all data should be copied over
        test_case.assertEqual(orig_info.start, copied_info.start)
        test_case.assertEqual(orig_info.end, copied_info.end)
        # annotations should be copied over
        orig_annotations = await node.annotation_get("/original/stream1")
        copied_annotations = await node.annotation_get("/copy/stream1")
        test_case.assertEqual(len(orig_annotations), len(copied_annotations))
        # event stream should be copied over
        orig_events = await node.event_stream_read_list("/original/events")
        copied_events = await node.event_stream_read_list("/copy/events")
        test_case.assertListEqual(orig_events, copied_events)
        # clean up
        await node.folder_delete("/copy", recursive=True)
        try:
            await node.folder_get("/copy")
            raise test_case.fail("folder not deleted")
        except errors.ApiError as e:
            test_case.assertIn(ApiErrorMessages.folder_does_not_exist, str(e))
        await node.close()
    asyncio.run(_validate())
    print("OK")

def test_copy_data_range():
    print("copying data range...",end="")
    runner = CliRunner()
    result = runner.invoke(main, f"folder copy /original /copy_range --start {ts2h(t8)} --end {ts2h(tB+1)}".split(" "), input="Y\n")
    _assert_success(result)
    async def _validate():
        node = api.get_node()
        copied_info = await node.data_stream_info("/copy/stream1")
        # data range should be copied over
        test_case.assertEqual(t8, copied_info.start)
        test_case.assertAlmostEqual(tB, copied_info.end, delta=2*60*1e6) # within 2 minutes
        # only annotations in the range be copied over
        copied_annotations = await node.annotation_get("/copy/stream1")
        test_case.assertEqual(len(copied_annotations), 1)
        test_case.assertEqual(copied_annotations[0].title, "note2")
        # events in the range should be copied over
        copied_events = await node.event_stream_read_list("/copy/events")
        test_case.assertListEqual([e.start_time for e in copied_events], [t8, t9, tA, tB])
        await node.close()
        # clean up
        await node.folder_delete("/copy", recursive=True)
        try:
            await node.folder_get("/copy")
            raise test_case.fail("folder not deleted")
        except errors.ApiError as e:
            test_case.assertIn(ApiErrorMessages.folder_does_not_exist, str(e))
        await node.close()
    asyncio.run(_validate())
    print("OK")

async def assert_has_intervals(node, stream, expected_intervals):
    actual_intervals = await node.data_intervals(stream)
    test_case.assertEqual(len(actual_intervals), len(expected_intervals))
    for actual, expected in zip(actual_intervals, expected_intervals):
        test_case.assertAlmostEqual(actual[0], expected[0], delta=2e6)
        test_case.assertAlmostEqual(actual[1], expected[1], delta=2e6)

async def print_intervals(node, stream):
    intervals = await node.data_intervals(stream)
    # expect /filtered/median2b to span t4 to tC
    print(f"=== {stream} intervals ====")
    for start,end in intervals:
        print(f"\t{ts2h(start)} -> {ts2h(end)}")
    print("==============================")


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

if __name__ == "__main__":
    time.sleep(8)  # wait for jouled to boot
    asyncio.run(setup())
    test_copy_all_data()
    test_process_data()
    test_backup_data()
