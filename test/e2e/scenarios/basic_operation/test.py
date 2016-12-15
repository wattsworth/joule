#!/usr/bin/python3
import time
import sys
import re
import numpy as np
sys.path.append("/module_scripts")  # add e2eutils
from e2eutils import joule as joule_cmd
from e2eutils import nilmtool as nilmtool_cmd


def main():
    time.sleep(8)  # wait for jouled to boot
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
    modules = joule_cmd.modules()
    assert(len(modules) == 4)  # normal1,normal2,filter,broken
    for module in modules:
        title = module[joule_cmd.MODULES_TITLE_FIELD]
        status = module[joule_cmd.MODULES_STATUS_FIELD]
        if(title['name'] in ['Normal1', 'Normal2', 'Filter']):
            assert status == joule_cmd.MODULES_STATUS_RUNNING, "%s status=%s" % (title[
                                                                                 'name'], status)
        elif(title['name'] == 'Broken'):
            pass
        else:
            assert(0)  # unexpected module in status report


def check_data():
    """
    Test: check data inserted into nilmdb
    Goal:
      /normal1/data is int32_1, has 1 interval with >500 samples
      /normal2/subpath/data  is int32_1, has multiple intervals each with 100 samples
      /broken/data is float64_1, has separated intervals of data
      both normal1 and normal2 have decimations
    """
    normal1_path = "/normal1/data"
    normal2_path = "/normal2/subpath/data"
    broken_path = "/broken/data"
    filter1_path = "/filter1/data"
    filter2_path = "/filter2/data"
    for path in [normal1_path, normal2_path, filter1_path, filter2_path]:
        # 1.) check streams have one continuous interval
        base_intervals = nilmtool_cmd.intervals(path)
        decim_intervals = nilmtool_cmd.intervals(
            path + "~decim-16")  # check level 2 decimation
        assert len(base_intervals) == 1,\
            "%s has %d intervals"%(path, len(base_intervals))
        assert len(decim_intervals) == 1,\
            "%s has %d intervals"%(path+"~decim-16", len(decim_intervals))
        # 2.) make sure this interval has data in it
        num_samples = nilmtool_cmd.data_count(path)
        assert(num_samples > 500)
        # 3.) make sure decimations have data
        assert(nilmtool_cmd.is_decimated(path))

    # the broken module should have multiple intervals (each restart)
    base_intervals = nilmtool_cmd.intervals(broken_path)
    decim_intervals = nilmtool_cmd.intervals(broken_path + "~decim-16")
    assert len(base_intervals) > 1,\
        "%s has %d intervals"%(broken_path, len(base_intervals))
    assert len(decim_intervals) > 1,\
        "%s has %d intervals"%(broken_path+"~decim-16", len(decim_intervals))

    for interval in base_intervals:
        num_samples = nilmtool_cmd.data_count(broken_path, interval)
        assert(num_samples == 100)
    assert(nilmtool_cmd.is_decimated(broken_path))

    # verify stream layouts
    assert nilmtool_cmd.layout(
        normal1_path) == "int32_1", nilmtool_cmd.layout(normal1_path)
    assert nilmtool_cmd.layout(normal2_path) == "int32_1"
    assert nilmtool_cmd.layout(filter1_path) == "float32_1"
    assert nilmtool_cmd.layout(filter2_path) == "float64_1"

    # verify the filter module executed correctly
    # check the first 2000 rows, the filter won't have all the source data because
    # the process was stopped
    expected_data = nilmtool_cmd.data_extract(normal1_path)
    expected_data[:, 1:] *= 2.0
    actual_data = nilmtool_cmd.data_extract(filter1_path)
    np.testing.assert_almost_equal(
        actual_data[:2000, :], expected_data[:2000, :])

    expected_data = nilmtool_cmd.data_extract(normal2_path)
    expected_data[:, 1:] *= 3.0
    actual_data = nilmtool_cmd.data_extract(filter2_path)
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
        logs = joule_cmd.logs(module_name)
        num_starts = len(re.findall(joule_cmd.LOG_STARTING_STRING, logs))
        assert(num_starts == 1)

    logs = joule_cmd.logs("Broken")
    num_starts = len(re.findall(joule_cmd.LOG_STARTING_STRING, logs))
    assert(num_starts > 1)

if __name__ == "__main__":
    main()
    print("OK")
