#!/usr/bin/python3
import time
import re
import numpy as np
from joule.testing.e2eutils import joule
from joule.testing.e2eutils import nilmtool


def main():
    time.sleep(8)  # wait for jouled to boot
    print( joule.logs("Filter"))
    check_modules()
    check_data()
    check_logs()


def check_modules():
    """
    Test: check module status
    Goal:
      normal1: running some nonzero memory
      normal2: running some nonzero memory
      filter:  running some nonzero memory
      broken:  present (could be running or failed)
      misconfigured: not present b/c can't be loaded
    """
    modules = joule.modules()
    assert(len(modules) == 4)  # normal1,normal2,filter,broken
    for module in modules:
        title = module[joule.MODULES_TITLE_FIELD]
        status = module[joule.MODULES_STATUS_FIELD]
        if(title['name'] in ['Normal1', 'Normal2', 'Filter']):
            msg = "%s status=%s" % (title['name'], status)
            assert status == joule.MODULES_STATUS_RUNNING, msg
        elif(title['name'] == 'Broken'):
            pass
        else:
            assert(0)  # unexpected module in status report


def check_data():
    """
    Test: check data inserted into nilmdb
    Goal:
      /normal1/data is int32_1, has 1 interval with >500 samples
      /normal2/subpath/data  is int32_1, >1 intervals each with 100 samples
      /broken/data is float64_1, has separated intervals of data
      /filter3/data is float64_1, has separated intervals of data
      both normal1 and normal2 have decimations
    """
    normal1_path = "/normal1/data"
    normal2_path = "/normal2/subpath/data"
    broken_path = "/broken/data"
    filter1_path = "/filter1/data"
    filter2_path = "/filter2/data"
    for path in [normal1_path, normal2_path, filter1_path, filter2_path]:
        # 1.) check streams have one continuous interval
        base_intervals = nilmtool.intervals(path)
        decim_intervals = nilmtool.intervals(
            path + "~decim-16")  # check level 2 decimation
        assert len(base_intervals) == 1,\
            "%s has %d intervals" % (path, len(base_intervals))
        assert len(decim_intervals) == 1,\
            "%s has %d intervals" % (path+"~decim-16", len(decim_intervals))
        # 2.) make sure this interval has data in it
        num_samples = nilmtool.data_count(path)
        assert(num_samples > 500)
        # 3.) make sure decimations have data
        assert(nilmtool.is_decimated(path))

    # the broken module and its filtered output
    # should have multiple intervals (each restart)
    for path in [broken_path]:
        base_intervals = nilmtool.intervals(path)
        decim_intervals = nilmtool.intervals(path + "~decim-16")
        assert len(base_intervals) > 1,\
            "%s has %d intervals" % (path, len(base_intervals))
        assert len(decim_intervals) > 1,\
            "%s has %d intervals" % (path+"~decim-16", len(decim_intervals))

        for interval in base_intervals:
            num_samples = nilmtool.data_count(path, interval)
            assert(num_samples == 100)
        assert(nilmtool.is_decimated(path))

    # verify stream layouts
    assert nilmtool.layout(
        normal1_path) == "int32_1", nilmtool.layout(normal1_path)
    assert nilmtool.layout(normal2_path) == "int32_1"
    assert nilmtool.layout(filter1_path) == "float32_1"
    assert nilmtool.layout(filter2_path) == "float64_1"

    # verify the filter module executed correctly
    # check the first 2000 rows, the filter won't
    # have all the source data because the process was stopped
    expected_data = nilmtool.data_extract(normal1_path)
    expected_data[:, 1:] *= 2.0
    actual_data = nilmtool.data_extract(filter1_path)
    np.testing.assert_almost_equal(
        actual_data[:2000, :], expected_data[:2000, :])

    expected_data = nilmtool.data_extract(normal2_path)
    expected_data[:, 1:] *= 3.0
    actual_data = nilmtool.data_extract(filter2_path)
    np.testing.assert_almost_equal(
        actual_data[:2000, :], expected_data[:2000, :])


def check_logs():
    """
    Test: logs should contain info and stderr from modules
    Goal: 
      Normal1: says "starting" somewhere once
      Normal2: says "starting" somewhere once
      Filter: says "starting" somewhere once
      Broken: says "starting" and more than one "restarting"
      Misconfigured: no logs
    """
    for module_name in ["Normal1", "Normal2", "Filter"]:
        logs = joule.logs(module_name)
        num_starts = len(re.findall(joule.LOG_STARTING_STRING, logs))
        assert(num_starts == 1)

    logs = joule.logs("Broken")
    num_starts = len(re.findall(joule.LOG_STARTING_STRING, logs))
    assert(num_starts > 1)

    
if __name__ == "__main__":
    main()
    print("OK")
