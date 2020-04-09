from joule import LocalPipe
import unittest
import asyncio
import numpy as np
import numpy.matlib
import argparse

from tests import helpers
from joule.client.builtins.merge_filter import MergeFilter

WINDOW = 9
WIDTH = 4
REPS_PER_BLOCK = 9
NUM_BLOCKS = 3


class TestMergeFilter(helpers.AsyncTestCase):

    def test_computes_simple_merge(self):
        # m :  0 1 2 3 4 5 (all 1's)
        # s1:  3 4 5       (all 2's)
        # s2:  1 2 3 4 5   (all 3's)
        # ------------------
        # out: 3 4 5       (all 1,2,3's)
        cases = [
            # CASE 1: slaves start after master
            [([0, 1, 2, 3, 4, 5],  # *******
              [3, 4, 5],           #    ****
              [1, 2, 3, 4, 5]),    #  ******
             [3, 4, 5]],           #    ----
            # CASE 2: slaves start before master
            [([3, 4, 5],           #    ****
              [2, 3, 4, 5],        #  ******
              [1, 2, 3, 4, 5]),    # *******
             [3, 4, 5]],           #    ----
        ]
        for case in cases:
            self.run_simple_merge_case(inputs=case[0], expected=case[1])


    def run_simple_merge_case(self, inputs, expected):

        my_filter = MergeFilter()
        loop = asyncio.new_event_loop()
        master_data = np.vstack((inputs[0], np.ones((2, len(inputs[0]))))).T
        slave1_data = np.vstack((inputs[1], 2*np.ones((3, len(inputs[1]))))).T
        slave2_data = np.vstack((inputs[2], 3*np.ones((1, len(inputs[2]))))).T
        master = LocalPipe("float32_2", loop, name="master")
        slave1 = LocalPipe("float32_3", loop, name="slave1")
        slave2 = LocalPipe("float32_1", loop, name="slave2")
        output = LocalPipe("float32_6", loop, name="output")
        args = argparse.Namespace(master="master", pipes="unset")
        # seed the input data
        master.write_nowait(master_data)
        slave1.write_nowait(slave1_data)
        slave2.write_nowait(slave2_data)
        slave1.close_nowait()
        slave2.close_nowait()
        master.close_nowait()

        # run filter in an event loop
        loop.run_until_complete(my_filter.run(args,
                                              inputs={'master': master, 'slave1': slave1, 'slave2': slave2},
                                              outputs={'output': output}))
        result = output.read_nowait(flatten=True)
        expected_data = np.vstack((expected,
                                   np.ones((2, len(expected))),
                                   2*np.ones((3, len(expected))),
                                   3*np.ones((1, len(expected))))).T
        np.testing.assert_array_equal(expected_data, result)
        loop.close()
