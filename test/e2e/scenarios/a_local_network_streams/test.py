#!/usr/bin/python3
import time
import re
import subprocess
import numpy as np
from joule.testing.e2eutils import joule
from joule.testing.e2eutils import nilmtool


def main():
    time.sleep(8)  # wait for jouled to boot
    procs = start_standalone_procs()
    time.sleep(5)  # let procs run
    stop_standalone_procs(procs)
    check_modules()
    check_data()
    check_logs()

    
def start_standalone_procs():
    # proc1 reads /counting/base and writes to /counting/plus2
    scenario_dir = "/joule/test/e2e/scenarios/a_local_network_streams/"
    base_dir = scenario_dir+"standalone_modules/proc1/"
    args = ["/joule/test/e2e/module_scripts/adder.py",
            "3",
            "--module_config", base_dir + "module.conf",
            "--stream_configs", base_dir + "stream_configs"]
    p1 = subprocess.Popen(args)
    return [p1]


def stop_standalone_procs(procs):
    for proc in procs:
        proc.kill()

        
def check_modules():
    """
    Test: check module status
    Goal:
      counter: running some nonzero memory
      plus1: running some nonzero memory
    """
    modules = joule.modules()
    assert(len(modules) == 2)
    for module in modules:
        title = module[joule.MODULES_TITLE_FIELD]
        status = module[joule.MODULES_STATUS_FIELD]
        assert status == joule.MODULES_STATUS_RUNNING,\
            "%s status=%s" % (title['name'], status)
        

def check_data():
    """
    Test: check data inserted into nilmdb
    Goal:
      /counting/base is int32_1, even numbers, 1 interval with >300 samples
      /counting/plus1 is int32_1, data is base+1
      /counting/odds is int32_1, data is odd with step by 2

      all paths have decimations
    """
    base_path = "/counting/base"
    plus1_path = "/counting/plus1"
    plus3_path = "/counting/plus3"
    for path in [base_path, plus1_path, plus3_path]:
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
        assert(num_samples > 300)
        # 3.) make sure decimations have data
        assert(nilmtool.is_decimated(path))

    # verify stream layouts
    assert nilmtool.layout(base_path) == "int32_1"
    assert nilmtool.layout(plus1_path) == "int32_1"

    # verify the filter module executed correctly
    # check the first 2000 rows, the filter won't
    # have all the source data because the process was stopped
    expected_data = nilmtool.data_extract(base_path)
    expected_data[:, 1:] += 1.0
    actual_data = nilmtool.data_extract(plus1_path)
    np.testing.assert_almost_equal(
        actual_data[:500, :], expected_data[:500, :])
    actual_data = nilmtool.data_extract(plus3_path)
    expected_data = np.arange(actual_data[0, 1],
                              actual_data[-1, 1]+1,
                              10)
    np.testing.assert_equal(actual_data[:, 1],
                            expected_data)
    

def check_logs():
    """
    Test: logs should contain info and stderr from modules
    Goal: 
      counter: says "starting" somewhere once
      plus1: says "starting" somewhere once
    """
    for module_name in ["counter", "plus1"]:
        logs = joule.logs(module_name)
        num_starts = len(re.findall(joule.LOG_STARTING_STRING, logs))
        assert(num_starts == 1)

    
if __name__ == "__main__":
    main()
    print("OK")
