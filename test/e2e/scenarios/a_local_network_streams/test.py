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
            "--module_config", base_dir + "module.conf",
            "--stream_configs", base_dir + "stream_configs"]
    p1 = subprocess.Popen(args)
    base_dir = scenario_dir+"standalone_modules/proc2/"
    args = ["/joule/test/e2e/module_scripts/merge_sum.py",
            "--module_config", base_dir + "module.conf",
            "--stream_configs", base_dir + "stream_configs"]
    p2 = subprocess.Popen(args)
    return (p1, p2)


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
      /counting/base is int32_1, has 1 interval with >500 samples
      /counting/plus1 is int32_1, data is base+1
      /counting/plus2 is int32_1, data is base+2
      /counting/plus4 is int32_1, data is base+4

      all paths have decimations
    """
    base_path = "/counting/base"
    plus1_path = "/counting/plus1"
    plus2_path = "/counting/plus2"
    plus4_path = "/counting/plus4"
    for path in [base_path, plus1_path, plus2_path, plus4_path]:
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
        actual_data[:2000, :], expected_data[:2000, :])


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
