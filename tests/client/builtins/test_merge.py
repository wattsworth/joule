from joule import LocalPipe
import unittest
import asyncio
import numpy as np
import numpy.matlib
import argparse
import pdb

import unittest
from tests import helpers
from joule.client.builtins.merge_filter import MergeFilter

WINDOW = 9
WIDTH = 4
REPS_PER_BLOCK = 9
NUM_BLOCKS = 3


class TestMergeFilter(helpers.AsyncTestCase):

    def test_offset_streams(self):
        # m :  0 1 2 3 4 5 (all 1's)
        # s1:  3 4 5       (all 2's)
        # s2:  1 2 3 4 5   (all 3's)
        # ------------------
        # out: 3 4 5       (all 1,2,3's)
        cases = [
            # CASE 1: slaves start after master
            [([0, 1, 2, 3, 4, 5],  # *******
              [3, 4, 5],  # ****
              [1, 2, 3, 4, 5]),  # ******
             [3, 4, 5]],  # ----
            # CASE 2: slaves start before master
            [([3, 4, 5],  # ****
              [2, 3, 4, 5],  # ******
              [1, 2, 3, 4, 5]),  # *******
             [3, 4, 5]],  # ----
            # CASE 3: mixed
            [([2, 3, 4, 5],  # ****
              [0, 1, 2, 3, 4, 5],  # ******
              [3, 4, 5]),  # ***
             [3, 4, 5]],  # ---
        ]

        def run_case(inputs, expected, master_width):
            my_filter = MergeFilter()
            loop = asyncio.new_event_loop()
            master_data = np.vstack((inputs[0], np.ones((master_width, len(inputs[0]))))).T
            slave1_data = np.vstack((inputs[1], 2 * np.ones((3, len(inputs[1]))))).T
            slave2_data = np.vstack((inputs[2], 3 * np.ones((1, len(inputs[2]))))).T
            master = LocalPipe("float32_%d" % master_width, loop, name="master")
            slave1 = LocalPipe("float32_3", loop, name="slave1")
            slave2 = LocalPipe("float32_1", loop, name="slave2")
            output = LocalPipe("float32_%d" % (master_width + 4), loop, name="output")
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
                                       np.ones((master_width, len(expected))),
                                       2 * np.ones((3, len(expected))),
                                       3 * np.ones((1, len(expected))))).T
            np.testing.assert_array_equal(expected_data, result)
            loop.close()

        for case in cases:
            run_case(inputs=case[0], expected=case[1], master_width=1)
            run_case(inputs=case[0], expected=case[1], master_width=3)

    def test_early_master(self):
        # first master read does not overlap with any slave data
        VISUALIZE = False

        # Master: y=10x-212
        ts = np.arange(0, 1300, 10)
        master_data = np.array([ts, 10 * ts - 212]).T
        master = helpers.TestingPipe("float32_1", name="master")
        master.write_nowait(master_data[:10])
        master.write_nowait(master_data[10:20])
        master.write_nowait(master_data[20:])
        # Slave1: y=-3.3x+436
        ts = np.arange(500, 1000, 10)
        slave1_data = np.array([ts, -3.3 * ts + 436]).T
        slave1 = helpers.TestingPipe("float32_1", name="slave1")
        slave1.write_nowait(slave1_data)
        args = argparse.Namespace(master="master", pipes="unset")
        output = helpers.TestingPipe("float32_2", name="output")

        # run filter in an event loop
        loop = asyncio.new_event_loop()
        my_filter = MergeFilter()
        loop.run_until_complete(my_filter.run(args,
                                              inputs={'master': master,
                                                      'slave1': slave1},
                                              outputs={'output': output}))
        result = output.data_blocks[0]
        ts = result['timestamp']
        # check that the timestamps cover the correct range
        self.assertEqual(ts[0], 500)
        self.assertEqual(ts[-1], 990)

        # check the master
        master_actual = result['data'][:, 0]
        residual = (10 * ts - 212) - master_actual
        np.testing.assert_allclose(residual, 0)
        # check slave1
        slave1_actual = result['data'][:, 1]
        residual = (-3.3 * ts + 436) - slave1_actual
        np.testing.assert_allclose(residual, 0)

        # NOTE: this test is close but not perfect... hmmm
        np.testing.assert_allclose(residual, 0, rtol=1e-5, atol=1e-4)

        if VISUALIZE:
            from matplotlib import pyplot as plt
            for data in [master_data, slave1_data]:
                plt.plot(data[:, 0], data[:, 1], linewidth=1)

            plt.plot(result['timestamp'], result['data'], '--', linewidth=2)
            plt.show()
        loop.close()

    def test_early_slave(self):
        # first master read does not overlap with any slave data
        VISUALIZE = False

        # Master: y=-3x+400
        ts = np.arange(500, 1000, 10)
        master_data = np.array([ts, -3 * ts + 400]).T
        master = helpers.TestingPipe("float32_1", name="master")
        master.write_nowait(master_data)

        # Slave1: y=10x-212
        ts = np.arange(0, 1300, 10)
        slave1_data = np.array([ts, 10 * ts - 212]).T
        slave1 = helpers.TestingPipe("float32_1", name="slave1")
        slave1.write_nowait(slave1_data[:10])
        slave1.write_nowait(slave1_data[10:20])
        slave1.write_nowait(slave1_data[20:])

        # Slave2: y=-3.3x+436
        ts = np.arange(300, 900, 10)
        slave2_data = np.array([ts, -3.3 * ts + 436]).T
        slave2 = helpers.TestingPipe("float32_1", name="slave2")
        slave2.write_nowait(slave2_data)

        args = argparse.Namespace(master="master", pipes="unset")
        output = helpers.TestingPipe("float32_3", name="output")

        # run filter in an event loop
        loop = asyncio.new_event_loop()
        my_filter = MergeFilter()
        loop.run_until_complete(my_filter.run(args,
                                              inputs={'master': master,
                                                      'slave1': slave1,
                                                      'slave2': slave2},
                                              outputs={'output': output}))
        result = output.data_blocks[0]
        ts = result['timestamp']
        # check that the timestamps cover the correct range
        self.assertEqual(ts[0], 500)
        self.assertLessEqual(ts[-1], 1000)

        # check the master
        master_actual = result['data'][:, 0]
        residual = (-3 * ts + 400) - master_actual
        np.testing.assert_allclose(residual, 0)
        # check slave1
        slave1_actual = result['data'][:, 1]
        residual = (10 * ts - 212) - slave1_actual
        np.testing.assert_allclose(residual, 0)

        # check slave2
        slave2_actual = result['data'][:, 2]
        residual = (-3.3 * ts + 436) - slave2_actual
        # NOTE: this test is close but not perfect... hmmm
        np.testing.assert_allclose(residual, 0, rtol=1e-5, atol=1e-4)

        if VISUALIZE:
            from matplotlib import pyplot as plt
            for data in [master_data, slave1_data, slave2_data]:
                plt.plot(data[:, 0], data[:, 1], linewidth=1)

            plt.plot(result['timestamp'], result['data'], '--', linewidth=2)
            plt.show()
        loop.close()

    def test_no_overlap(self):
        # Master: y=10x-212
        ts = np.arange(0, 500, 1)
        master_data = np.array([ts, 10 * ts - 212]).T
        master = helpers.TestingPipe("float32_1", name="master")
        master.write_nowait(master_data[:100])
        master.write_nowait(master_data[100:200])
        master.write_nowait(master_data[200:])
        # Slave1: y=-3.3x+436
        ts = np.arange(510, 1000, 1)
        slave1_data = np.array([ts, -5 * ts + 436]).T
        slave1 = helpers.TestingPipe("float32_1", name="slave1")
        slave1.write_nowait(slave1_data[:150])
        slave1.write_nowait(slave1_data[150:350])
        slave1.write_nowait(slave1_data[350:])

        args = argparse.Namespace(master="master", pipes="unset")
        output = helpers.TestingPipe("float32_2", name="output")

        # run filter in an event loop
        loop = asyncio.new_event_loop()
        my_filter = MergeFilter()
        loop.run_until_complete(my_filter.run(args,
                                              inputs={'master': master,
                                                      'slave1': slave1},
                                              outputs={'output': output}))
        loop.close()
        # put together the data_blocks (should not be any interval breaks)
        # remove the interval close at the end
        self.assertEqual(len(output.data_blocks), 0)

    def test_multiple_blocks(self):
        # first master read does not overlap with any slave data
        VISUALIZE = False

        # Master: y=10x-212
        ts = np.arange(0, 500, 1)
        master_data = np.array([ts, 10 * ts - 212]).T
        master = helpers.TestingPipe("float32_1", name="master")
        master.write_nowait(master_data[:100])
        master.write_nowait(master_data[100:200])
        master.write_nowait(master_data[200:])
        # Slave1: y=-3.3x+436
        ts = np.arange(0, 500, 1)
        slave1_data = np.array([ts, -5 * ts + 436]).T
        slave1 = helpers.TestingPipe("float32_1", name="slave1")
        slave1.write_nowait(slave1_data[:150])
        slave1.write_nowait(slave1_data[150:350])
        slave1.write_nowait(slave1_data[350:])

        args = argparse.Namespace(master="master", pipes="unset")
        output = helpers.TestingPipe("float32_2", name="output")

        # run filter in an event loop
        loop = asyncio.new_event_loop()
        my_filter = MergeFilter()
        loop.run_until_complete(my_filter.run(args,
                                              inputs={'master': master,
                                                      'slave1': slave1},
                                              outputs={'output': output}))
        # put together the data_blocks (should not be any interval breaks)
        # remove the interval close at the end
        output.data_blocks.pop()
        result = np.hstack(output.data_blocks)
        ts = result['timestamp']
        # check that the timestamps cover the correct range
        self.assertEqual(ts[0], 0)
        self.assertEqual(ts[-1], 499)
        # no duplicate timestamps
        self.assertEqual(len(np.unique(ts)), len(master_data))

        # check the master
        master_actual = result['data'][:, 0]
        residual = (10 * ts - 212) - master_actual
        np.testing.assert_allclose(residual, 0)
        # check slave1
        slave1_actual = result['data'][:, 1]
        residual = (-5 * ts + 436) - slave1_actual
        np.testing.assert_allclose(residual, 0)

        # NOTE: this test is close but not perfect... hmmm
        np.testing.assert_allclose(residual, 0, rtol=1e-5, atol=1e-4)

        if VISUALIZE:
            from matplotlib import pyplot as plt
            for data in [master_data, slave1_data]:
                plt.plot(data[:, 0], data[:, 1], linewidth=1)

            plt.plot(result['timestamp'], result['data'], '--', linewidth=2)
            plt.show()
        loop.close()

    def test_interval_breaks(self):
        # realigns inputs after interval breaks
        # ---- THIS IS COMPLEX TO IMPLEMENT, NOT FULLY FUNCTIONAL -----

        # master:[0----100] [110-----------200]   [210------300]
        # slave1:   [50---------160] [170-----------230]
        # slave2: [10---------------------190] [205-----------310]
        # ========================================================
        # output:   [50-100][110-160][170-190] [205-230]

        # Master: y=10x-212
        ts = np.arange(0, 500, 1)
        master_data = np.array([ts, 10 * ts - 212]).T
        master = helpers.TestingPipe("float32_1", name="master")
        master.write_nowait(master_data[:100])
        master.close_interval_no_wait()
        master.write_nowait(master_data[110:200])
        master.close_interval_no_wait()
        master.write_nowait(master_data[210:300])

        # Slave1: y=-3x+436
        ts = np.arange(0, 500, 1)
        master_data = np.array([ts, -3 * ts + 436]).T
        slave1 = helpers.TestingPipe("float32_1", name="slave1")
        slave1.write_nowait(master_data[50:160])
        slave1.close_interval_no_wait()
        slave1.write_nowait(master_data[170:230])

        output = helpers.TestingPipe("float32_2", name="output")
        loop = asyncio.new_event_loop()
        my_filter = MergeFilter()
        args = argparse.Namespace(master="master", pipes="unset")
        loop.run_until_complete(my_filter.run(args,
                                              inputs={'master': master,
                                                      'slave1': slave1},
                                              outputs={'output': output}))
        loop.close()

    def test_different_arrival_rates(self):
        # merges multiple streams each arriving with different chunk sizes

        # All streams have the same data at the same rate, but they arrive
        # in different chunks. Expect all elements in the merged output to be the same
        VISUALIZE = False
        ts = np.arange(0, 1000)
        values = np.random.randn(1000, 1)
        data = np.hstack((ts[:, None], values))

        master = helpers.TestingPipe("float32_1", name="master")
        slave1 = helpers.TestingPipe("float32_1", name="slave1")
        slave2 = helpers.TestingPipe("float32_1", name="slave2")
        # seed the input data
        for block in np.split(data, [200, 354, 700]):
            master.write_nowait(block)
        for block in np.split(data, [155, 600, 652, 900]):
            slave1.write_nowait(block)
        for block in np.split(data, [100, 300, 600]):
            slave2.write_nowait(block)
        # run filter in an event loop
        loop = asyncio.new_event_loop()
        my_filter = MergeFilter()
        args = argparse.Namespace(master="master", pipes="unset")
        output = helpers.TestingPipe("float32_3", name="output")
        loop.run_until_complete(my_filter.run(args,
                                              inputs={'master': master,
                                                      'slave1': slave1,
                                                      'slave2': slave2},
                                              outputs={'output': output}))
        # put together the data_blocks (should not be any interval breaks)
        # remove the interval close at the end
        output.data_blocks.pop()
        for blk in output.data_blocks:
            self.assertIsNotNone(blk)
        result = np.hstack(output.data_blocks)
        # all elements should match the data
        np.testing.assert_array_almost_equal(result['data'][:, 0][:, None], values)
        np.testing.assert_array_almost_equal(result['data'][:, 1][:, None], values)
        np.testing.assert_array_almost_equal(result['data'][:, 2][:, None], values)

        if VISUALIZE:
            from matplotlib import pyplot as plt
            f, (ax1, ax2) = plt.subplots(2, 1, sharey=True)
            ax1.plot(result['timestamp'], result['data'][:, 0], linewidth=4)
            ax1.plot(result['timestamp'], result['data'][:, 1], linewidth=1)
            ax1.set_title('Slave 1 vs Master')

            ax2.plot(result['timestamp'], result['data'][:, 0], linewidth=4)
            ax2.plot(result['timestamp'], result['data'][:, 2], linewidth=1)
            ax2.set_title('Slave 2 vs Master')

            plt.show()

    def test_static_cases(self):
        # merges streams with several different data rates
        # 1) Master == Slave1
        # 2) Master  > Slave2
        # 3) Master  < Slave3
        # 4) Master != Slave4 (timestamps randomly offset)
        VISUALIZE = False

        # Master: y=10x-212
        ts = np.arange(127, 1000, 10)
        master_data = np.array([ts, 10 * ts - 212]).T

        # Slave1: y=-3x+436
        slave1_data = np.array([ts, -3 * ts + 436]).T

        # Slave 2: y=0.5x+101
        ts = np.arange(200, 1000, 47)
        slave2_data = np.array([ts, 0.5 * ts + 101]).T

        # Slave 3: y=8x+3000
        ts = np.arange(0, 756, 3)
        slave3_data = np.array([ts, 8 * ts - 3000]).T

        # Slave 4: y=-15x+6000
        ts = np.unique([np.round(x) for x in np.random.uniform(100, 1100, 478)])
        slave4_data = np.array([ts, -15 * ts + 6000]).T

        def run() -> np.ndarray:
            my_filter = MergeFilter()
            loop = asyncio.new_event_loop()
            master = helpers.TestingPipe("float32_1", name="master")
            slave1 = helpers.TestingPipe("float32_1", name="slave1")
            slave2 = helpers.TestingPipe("float32_1", name="slave2")
            slave3 = helpers.TestingPipe("float32_1", name="slave3")
            slave4 = helpers.TestingPipe("float32_1", name="slave4")
            output = helpers.TestingPipe("float32_5", name="output")
            args = argparse.Namespace(master="master", pipes="unset")
            # seed the input data
            master.write_nowait(master_data)
            slave1.write_nowait(slave1_data)
            slave2.write_nowait(slave2_data)
            slave3.write_nowait(slave3_data)
            slave4.write_nowait(slave4_data)

            # run filter in an event loop
            loop.run_until_complete(my_filter.run(args,
                                                  inputs={'master': master,
                                                          'slave1': slave1,
                                                          'slave2': slave2,
                                                          'slave3': slave3,
                                                          'slave4': slave4},
                                                  outputs={'output': output}))
            loop.close()
            return output.data_blocks[0]

        result = run()
        ts = result['timestamp']
        # check that the timestamps cover the correct range
        self.assertGreaterEqual(ts[0], 200)
        self.assertLessEqual(ts[-1], 756)

        # check the master
        master_actual = result['data'][:, 0]
        residual = (10 * ts - 212) - master_actual
        np.testing.assert_allclose(residual, 0)
        # check slave1
        slave1_actual = result['data'][:, 1]
        residual = (-3 * ts + 436) - slave1_actual
        np.testing.assert_allclose(residual, 0)
        # check slave2
        slave2_actual = result['data'][:, 2]
        residual = (0.5 * ts + 101) - slave2_actual
        np.testing.assert_allclose(residual, 0)
        # check slave3
        slave3_actual = result['data'][:, 3]
        residual = (8 * ts - 3000) - slave3_actual
        np.testing.assert_allclose(residual, 0)

        if VISUALIZE:
            from matplotlib import pyplot as plt
            for data in [master_data, slave1_data,
                         slave2_data, slave3_data, slave4_data]:
                plt.plot(data[:, 0], data[:, 1], linewidth=1)

            plt.plot(result['timestamp'], result['data'], '--', linewidth=2)
            plt.show()
