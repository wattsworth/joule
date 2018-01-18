#!/usr/bin/python3
import time
import re
import subprocess
import numpy as np
from joule.testing.e2eutils import joule
from joule.testing.e2eutils import nilmtool


NILMDB_URL = "http://127.0.0.1/nilmdb"
#NILMDB_URL = "http://nilmdb"


def main():
    time.sleep(8)  # wait for jouled to boot
    procs = start_standalone_procs1()
    time.sleep(4)  # let procs run
    stop_standalone_procs(procs)
    time.sleep(8) # close sockets
    procs = start_standalone_procs2()
    time.sleep(1) # let procs run
    stop_standalone_procs(procs)
    time.sleep(4)  # close sockets
    check_modules()
    check_data()
    check_logs()

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
    assert p1a.stderr.find("/counting/plus3") != -1

    # proc2 tries to read from /bad/path but fails
    p2 = subprocess.run(build_standalone_args("proc2"),
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        universal_newlines=True)
    assert p2.stderr.find("/bad/path") != -1

    return [p1]


def start_standalone_procs2():
    # proc3 tries to write to /counting/plus3 with wrong dtype
    p3 = subprocess.run(build_standalone_args("proc3"),
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        universal_newlines=True)
    assert p3.stderr.find("datatype") != -1

    # proc4 reads /counting/base and writes to /counting/plus3
    p1 = subprocess.Popen(build_standalone_args("proc1"))

    try:
        nilmtool.create_stream("/exists/int8", "int8_4", url=NILMDB_URL)
    except:
        pass
    # proc5 tries to write to /exists/int8 with wrong element count
    p4 = subprocess.run(build_standalone_args("proc4"),
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        universal_newlines=True)
    assert p4.stderr.find("/exists/int8") != -1

    return [p1]


def build_standalone_args(proc_dir):
    scenario_dir = "/joule/tests/e2e/scenarios/a_local_network_streams/"
    base_dir = scenario_dir+"standalone_modules/"+proc_dir+"/"
    return ["/joule/tests/e2e/module_scripts/adder.py",
            "3",
            "--module_config", base_dir + "module.conf",
            "--stream_configs", base_dir + "stream_configs"]


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
      /counting/base is int32_1, 1 interval with >300 samples
      /counting/plus1 is int32_1, data is base+1
      /counting/plus3 is int32_1, data is base+3

      all paths have decimations
    """
    base_path = "/counting/base"
    plus1_path = "/counting/plus1"
    plus3_path = "/counting/plus3"
    for path in [base_path, plus1_path]:
        # 1.) check streams have one continuous interval
        base_intervals = nilmtool.intervals(path, url=NILMDB_URL)
        decim_intervals = nilmtool.intervals(
            path + "~decim-16", url=NILMDB_URL)  # check level 2 decimation
        assert len(base_intervals) == 1,\
            "%s has %d intervals" % (path, len(base_intervals))
        assert len(decim_intervals) == 1,\
            "%s has %d intervals" % (path+"~decim-16", len(decim_intervals))
        # 2.) make sure this interval has data in it
        num_samples = nilmtool.data_count(path, url=NILMDB_URL)
        assert(num_samples > 300)
        # 3.) make sure decimations have data
        assert(nilmtool.is_decimated(path, url=NILMDB_URL))

    for path in [plus3_path]:
        # 1.) check stream has two intervals
        base_intervals = nilmtool.intervals(path, url=NILMDB_URL)
        decim_intervals = nilmtool.intervals(
            path + "~decim-16", url=NILMDB_URL)  # check level 2 decimation
        assert len(base_intervals) == 2,\
            "%s has %d intervals" % (path, len(base_intervals))
        assert len(decim_intervals) == 2,\
            "%s has %d intervals" % (path+"~decim-16", len(decim_intervals))
        # 2.) make sure this interval has data in it
        num_samples = nilmtool.data_count(path, url=NILMDB_URL)
        assert(num_samples > 300)
        # 3.) make sure decimations have data
        assert(nilmtool.is_decimated(path, url=NILMDB_URL))

    # verify stream layouts
    assert nilmtool.layout(base_path, url=NILMDB_URL) == "int32_1"
    assert nilmtool.layout(plus1_path, url=NILMDB_URL) == "int32_1"
    assert nilmtool.layout(plus3_path, url=NILMDB_URL) == "int32_1"

    # verify the filter module executed correctly
    # check the first 2000 rows, the filter won't
    # have all the input data because the process was stopped
    expected_data = nilmtool.data_extract(base_path, url=NILMDB_URL)
    expected_data[:, 1:] += 1.0
    actual_data = nilmtool.data_extract(plus1_path, url=NILMDB_URL)
    np.testing.assert_almost_equal(
        actual_data[:500, :], expected_data[:500, :])
    actual_data = nilmtool.data_extract(plus3_path, url=NILMDB_URL)
    # expect all data is a multiple of 13 and monotonic
    for val in actual_data[:, 1]:
        assert (val % 10) == 3, "%d is not good" % val
    assert min(np.diff(actual_data[:, 1])) == 10, "%d is bad" % min(np.diff(actual_data[:, 1]))
    

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
