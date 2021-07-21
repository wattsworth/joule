from joule import LocalPipe
import unittest
import asyncio
import numpy as np
import argparse
import pdb

import unittest
from tests import helpers
from joule.client.builtins.merge_filter import MergeFilter
from joule.errors import EmptyPipeError
from icecream import ic

WINDOW = 9
WIDTH = 4
REPS_PER_BLOCK = 9
NUM_BLOCKS = 3


class TestMergeFilter(unittest.TestCase):

    def test_offset_streams(self):
        # m :  0 1 2 3 4 5 (all 1's)
        # s1:  3 4 5       (all 2's)
        # s2:  1 2 3 4 5   (all 3's)
        # ------------------
        # out: 3 4 5       (all 1,2,3's)
        cases = [
            # CASE 1: secondarys start after primary
            [([0, 1, 2, 3, 4, 5],  # *******
              [3, 4, 5],  # ****
              [1, 2, 3, 4, 5]),  # ******
             [3, 4, 5]],  # ----
            # CASE 2: secondarys start before primary
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

        async def run_case(inputs, expected, primary_width):
            my_filter = MergeFilter()
            primary_data = np.vstack((inputs[0], np.ones((primary_width, len(inputs[0]))))).T
            secondary1_data = np.vstack((inputs[1], 2 * np.ones((3, len(inputs[1]))))).T
            secondary2_data = np.vstack((inputs[2], 3 * np.ones((1, len(inputs[2]))))).T
            primary = LocalPipe("float32_%d" % primary_width, name="primary")
            secondary1 = LocalPipe("float32_3", name="secondary1")
            secondary2 = LocalPipe("float32_1", name="secondary2")
            output = LocalPipe("float32_%d" % (primary_width + 4), name="output")
            args = argparse.Namespace(primary="primary", pipes="unset")
            # seed the input data
            await primary.write(primary_data)
            await secondary1.write(secondary1_data)
            await secondary2.write(secondary2_data)
            await secondary1.close()
            await secondary2.close()
            await primary.close()

            # run filter in an event loop
            await my_filter.run(args,
                                inputs={'primary': primary, 'secondary1': secondary1, 'secondary2': secondary2},
                                outputs={'output': output})
            result = output.read_nowait(flatten=True)
            expected_data = np.vstack((expected,
                                       np.ones((primary_width, len(expected))),
                                       2 * np.ones((3, len(expected))),
                                       3 * np.ones((1, len(expected))))).T
            np.testing.assert_array_equal(expected_data, result)

        for case in cases:
            asyncio.run(run_case(inputs=case[0], expected=case[1], primary_width=1))
            asyncio.run(run_case(inputs=case[0], expected=case[1], primary_width=3))

    def test_early_primary(self):
        # first primary read does not overlap with any secondary data
        VISUALIZE = False

        async def _run():

            # Primary: y=10x-212
            ts = np.arange(0, 1300, 10)
            primary_data = np.array([ts, 10 * ts - 212]).T
            primary = helpers.TestingPipe("float32_1", name="primary")
            await primary.write(primary_data[:10])
            await primary.write(primary_data[10:20])
            await primary.write(primary_data[20:])
            await primary.close()

            # Secondary1: y=-3.3x+436
            ts = np.arange(500, 1000, 10)
            secondary1_data = np.array([ts, -3.3 * ts + 436]).T
            secondary1 = helpers.TestingPipe("float32_1", name="secondary1")
            await secondary1.write(secondary1_data[:20])
            await secondary1.write(secondary1_data[20:30])
            await secondary1.write(secondary1_data[30:])
            await secondary1.close()

            args = argparse.Namespace(primary="primary", pipes="unset")
            output = LocalPipe("float32_2", name="output")

            # run filter in an event loop
            my_filter = MergeFilter()

            await my_filter.run(args,
                                inputs={'primary': primary,
                                        'secondary1': secondary1},
                                outputs={'output': output})

            result = await output.read_all()
            ts = result['timestamp']
            # check that the timestamps cover the correct range
            self.assertEqual(ts[0], 500)
            self.assertEqual(ts[-1], 990)

            # check the primary
            primary_actual = result['data'][:, 0]
            residual = (10 * ts - 212) - primary_actual
            np.testing.assert_allclose(residual, 0)
            # check secondary1
            secondary1_actual = result['data'][:, 1]
            residual = (-3.3 * ts + 436) - secondary1_actual
            np.testing.assert_allclose(residual, 0)

            # NOTE: this test is close but not perfect... hmmm
            np.testing.assert_allclose(residual, 0, rtol=1e-5, atol=1e-4)

            if VISUALIZE:
                from matplotlib import pyplot as plt
                for data in [primary_data, secondary1_data]:
                    plt.plot(data[:, 0], data[:, 1], linewidth=1)

                    plt.plot(result['timestamp'], result['data'], '--', linewidth=2)
                    plt.show()

        asyncio.run(_run())

    def test_early_secondary(self):
        # first primary read does not overlap with any secondary data
        VISUALIZE = False

        async def _run():
            # Primary: y=-3x+400
            ts = np.arange(500, 1000, 10)
            primary_data = np.array([ts, -3 * ts + 400]).T
            primary = helpers.TestingPipe("float32_1", name="primary")
            # break this up so it takes multiple reads to finish
            primary.write_nowait(primary_data[:30])
            primary.write_nowait(primary_data[30:35])
            primary.write_nowait(primary_data[35:45])
            primary.write_nowait(primary_data[45:])
            await primary.close()
            # Secondary1: y=10x-212
            ts = np.arange(0, 1300, 10)
            secondary1_data = np.array([ts, 10 * ts - 212]).T
            secondary1 = helpers.TestingPipe("float32_1", name="secondary1")
            secondary1.write_nowait(secondary1_data[:10])
            secondary1.write_nowait(secondary1_data[10:20])
            secondary1.write_nowait(secondary1_data[20:])
            await secondary1.close()
            # Secondary2: y=-3.3x+436
            ts = np.arange(300, 900, 10)
            secondary2_data = np.array([ts, -3.3 * ts + 436]).T
            secondary2 = helpers.TestingPipe("float32_1", name="secondary2")
            secondary2.write_nowait(secondary2_data)
            await secondary2.close()
            args = argparse.Namespace(primary="primary", pipes="unset")
            output = helpers.TestingPipe("float32_3", name="output")

            # run filter in an event loop
            my_filter = MergeFilter()
            await my_filter.run(args,
                                inputs={'primary': primary,
                                        'secondary1': secondary1,
                                        'secondary2': secondary2},
                                outputs={'output': output})
            result = output.data_blocks[0]
            ts = result['timestamp']
            # check that the timestamps cover the correct range
            self.assertEqual(ts[0], 500)
            self.assertLessEqual(ts[-1], 1000)

            # check the primary
            primary_actual = result['data'][:, 0]
            residual = (-3 * ts + 400) - primary_actual
            np.testing.assert_allclose(residual, 0)
            # check secondary1
            secondary1_actual = result['data'][:, 1]
            residual = (10 * ts - 212) - secondary1_actual
            np.testing.assert_allclose(residual, 0)

            # check secondary2
            secondary2_actual = result['data'][:, 2]
            residual = (-3.3 * ts + 436) - secondary2_actual
            # NOTE: this test is close but not perfect... hmmm
            np.testing.assert_allclose(residual, 0, rtol=1e-5, atol=1e-4)

            if VISUALIZE:
                import matplotlib
                matplotlib.use('TkAgg')
                from matplotlib import pyplot as plt

                for data in [primary_data, secondary1_data, secondary2_data]:
                    plt.plot(data[:, 0], data[:, 1], linewidth=1)

                plt.plot(result['timestamp'], result['data'], '--', linewidth=2)
                plt.show()

        asyncio.run(_run())

    def test_no_overlap(self):

        async def _run():
            # Primary: y=10x-212
            ts = np.arange(0, 500, 1)
            primary_data = np.array([ts, 10 * ts - 212]).T
            primary = helpers.TestingPipe("float32_1", name="primary")
            await primary.write(primary_data[:100])
            await primary.write(primary_data[100:200])
            await primary.write(primary_data[200:])
            await primary.close()
            # Secondary1: y=-3.3x+436
            ts = np.arange(510, 1000, 1)
            secondary1_data = np.array([ts, -5 * ts + 436]).T
            secondary1 = helpers.TestingPipe("float32_1", name="secondary1")
            await secondary1.write(secondary1_data[:150])
            await secondary1.write(secondary1_data[150:350])
            await secondary1.write(secondary1_data[350:])
            await secondary1.close()

            args = argparse.Namespace(primary="primary", pipes="unset")
            output = LocalPipe("float32_2", name="output")

            # run filter in an event loop
            my_filter = MergeFilter()
            await my_filter.run(args,
                                inputs={'primary': primary,
                                        'secondary1': secondary1},
                                outputs={'output': output})

            self.assertTrue(output.is_empty())
            with self.assertRaises(EmptyPipeError):
                await output.read()

        asyncio.run(_run())

    def test_multiple_blocks(self):
        # first primary read does not overlap with any secondary data
        VISUALIZE = False

        async def _run():
            # Primary: y=10x-212
            ts = np.arange(0, 500, 1)
            primary_data = np.array([ts, 10 * ts - 212]).T
            primary = helpers.TestingPipe("float32_1", name="primary")
            primary.write_nowait(primary_data[:100])
            primary.write_nowait(primary_data[100:200])
            primary.write_nowait(primary_data[200:])
            await primary.close()
            # Secondary1: y=-3.3x+436
            ts = np.arange(0, 500, 1)
            secondary1_data = np.array([ts, -5 * ts + 436]).T
            secondary1 = helpers.TestingPipe("float32_1", name="secondary1")
            secondary1.write_nowait(secondary1_data[:150])
            secondary1.write_nowait(secondary1_data[150:350])
            secondary1.write_nowait(secondary1_data[350:])
            await secondary1.close()

            args = argparse.Namespace(primary="primary", pipes="unset")
            output = LocalPipe("float32_2", name="output")

            # run filter in an event loop
            my_filter = MergeFilter()
            await my_filter.run(args,
                                inputs={'primary': primary,
                                        'secondary1': secondary1},
                                outputs={'output': output})
            # put together the data_blocks (should not be any interval breaks)
            # remove the interval close at the end
            result = await output.read_all()
            ts = result['timestamp']
            # check that the timestamps cover the correct range
            self.assertEqual(ts[0], 0)
            self.assertEqual(ts[-1], 499)
            # no duplicate timestamps
            self.assertEqual(len(np.unique(ts)), len(primary_data))

            # check the primary
            primary_actual = result['data'][:, 0]
            residual = (10 * ts - 212) - primary_actual
            np.testing.assert_allclose(residual, 0)
            # check secondary1
            secondary1_actual = result['data'][:, 1]
            residual = (-5 * ts + 436) - secondary1_actual
            np.testing.assert_allclose(residual, 0)

            # NOTE: this test is close but not perfect... hmmm
            np.testing.assert_allclose(residual, 0, rtol=1e-5, atol=1e-4)

            if VISUALIZE:
                from matplotlib import pyplot as plt
                for data in [primary_data, secondary1_data]:
                    plt.plot(data[:, 0], data[:, 1], linewidth=1)

                plt.plot(result['timestamp'], result['data'], '--', linewidth=2)
                plt.show()

        asyncio.run(_run())

    @unittest.skip('TODO: needs more analysis')
    def test_interval_breaks(self):
        # realigns inputs after interval breaks

        # primary:[0----100] [110-----------200]   [210------300]
        # secondary1:   [50---------160] [170-----------230]
        # secondary2: [10---------------------190] [205-----------310]
        # ========================================================
        # output:   [50-100][110-160][170-190] [205-230]

        # Primary: y=10x-212
        async def _run():
            ts = np.arange(0, 500, 1)
            primary_data = np.array([ts, 10 * ts - 212]).T
            primary = LocalPipe("float32_1", name="primary")
            await primary.write(primary_data[:101])
            await primary.close_interval()
            await primary.write(primary_data[110:201])
            await primary.close_interval()
            await primary.write(primary_data[210:301])
            await primary.close()

            # Secondary1: y=-3x+436
            ts = np.arange(0, 500, 1)
            secondary_data = np.array([ts, -3 * ts + 436]).T
            secondary1 = LocalPipe("float32_1", name="secondary1")
            await secondary1.write(secondary_data[50:161])
            await secondary1.close_interval()
            await secondary1.write(secondary_data[170:231])
            await secondary1.close()

            # Secondary2: y=30x+210
            ts = np.arange(0, 500, 1)
            secondary_data = np.array([ts, 30 * ts + 210]).T
            secondary2 = LocalPipe("float32_1", name="secondary2")
            await secondary2.write(secondary_data[10:191])
            await secondary2.close_interval()
            await secondary2.write(secondary_data[205:311])
            await secondary2.close()

            output = LocalPipe("float32_3", name="output")
            my_filter = MergeFilter()
            args = argparse.Namespace(primary="primary", pipes="unset")
            await my_filter.run(args,
                                inputs={'primary': primary,
                                        'secondary1': secondary1,
                                        'secondary2': secondary2},
                                outputs={'output': output})
            chunk = await output.read()
            self.assertEqual(chunk['timestamp'][0], 50)
            self.assertEqual(chunk['timestamp'][-1], 100)
            self.assertTrue(output.end_of_interval)
            output.consume(len(chunk))

            chunk = await output.read()
            self.assertEqual(chunk['timestamp'][0], 110)
            self.assertEqual(chunk['timestamp'][-1], 160)
            self.assertTrue(output.end_of_interval)
            output.consume(len(chunk))

            chunk = await output.read()
            self.assertEqual(chunk['timestamp'][0], 170)
            self.assertEqual(chunk['timestamp'][-1], 190)
            self.assertTrue(output.end_of_interval)
            output.consume(len(chunk))

            chunk = await output.read()
            self.assertEqual(chunk['timestamp'][0], 210)
            self.assertEqual(chunk['timestamp'][-1], 230)
            output.consume(len(chunk))

            self.assertTrue(output.is_empty())

        asyncio.run(_run())

    def test_different_arrival_rates(self):
        # merges multiple streams each arriving with different chunk sizes

        # All streams have the same data at the same rate, but they arrive
        # in different chunks. Expect all elements in the merged output to be the same
        VISUALIZE = False

        async def _run():
            ts = np.arange(0, 1000)
            values = np.random.randn(1000, 1)
            data = np.hstack((ts[:, None], values))

            primary = helpers.TestingPipe("float32_1", name="primary")
            secondary1 = helpers.TestingPipe("float32_1", name="secondary1")
            secondary2 = helpers.TestingPipe("float32_1", name="secondary2")
            # seed the input data
            for block in np.split(data, [200, 354, 700, 800, 930]):
                primary.write_nowait(block)
            for block in np.split(data, [155, 600, 652, 900]):
                secondary1.write_nowait(block)
            for block in np.split(data, [100, 300, 600]):
                secondary2.write_nowait(block)
            await primary.close()
            await secondary1.close()
            await secondary2.close()
            # run filter in an event loop
            my_filter = MergeFilter()
            args = argparse.Namespace(primary="primary", pipes="unset")
            output = LocalPipe("float32_3", name="output")
            await my_filter.run(args,
                                inputs={'primary': primary,
                                        'secondary1': secondary1,
                                        'secondary2': secondary2},
                                outputs={'output': output})
            # put together the data_blocks (should not be any interval breaks)
            # remove the interval close at the end

            result = await output.read()
            output.consume(len(result))
            self.assertTrue(output.is_empty())
            # all elements should match the data
            np.testing.assert_array_almost_equal(result['data'][:, 0][:, None], values)
            np.testing.assert_array_almost_equal(result['data'][:, 1][:, None], values)
            np.testing.assert_array_almost_equal(result['data'][:, 2][:, None], values)

            if VISUALIZE:
                from matplotlib import pyplot as plt
                f, (ax1, ax2) = plt.subplots(2, 1, sharey=True)
                ax1.plot(result['timestamp'], result['data'][:, 0], linewidth=4)
                ax1.plot(result['timestamp'], result['data'][:, 1], linewidth=1)
                ax1.set_title('Secondary 1 vs primary')

                ax2.plot(result['timestamp'], result['data'][:, 0], linewidth=4)
                ax2.plot(result['timestamp'], result['data'][:, 2], linewidth=1)
                ax2.set_title('Secondary 2 vs primary')

                plt.show()

        asyncio.run(_run())

    def test_static_cases(self):
        # merges streams with several different data rates
        # 1) primary == Secondary1
        # 2) primary  > Secondary2
        # 3) primary  < Secondary3
        # 4) primary != Secondary4 (timestamps randomly offset)
        VISUALIZE = False

        # primary: y=10x-212
        ts = np.arange(127, 1000, 10)
        primary_data = np.array([ts, 10 * ts - 212]).T

        # Secondary1: y=-3x+436
        secondary1_data = np.array([ts, -3 * ts + 436]).T

        # Secondary 2: y=0.5x+101
        ts = np.arange(200, 1000, 47)
        secondary2_data = np.array([ts, 0.5 * ts + 101]).T

        # Secondary 3: y=8x+3000
        ts = np.arange(0, 756, 3)
        secondary3_data = np.array([ts, 8 * ts - 3000]).T

        # Secondary 4: y=-15x+6000
        ts = np.unique([np.round(x) for x in np.random.uniform(100, 1100, 478)])
        secondary4_data = np.array([ts, -15 * ts + 6000]).T

        async def run() -> np.ndarray:
            my_filter = MergeFilter()
            primary = LocalPipe("float32_1", name="primary")
            secondary1 = LocalPipe("float32_1", name="secondary1")
            secondary2 = LocalPipe("float32_1", name="secondary2")
            secondary3 = LocalPipe("float32_1", name="secondary3")
            secondary4 = LocalPipe("float32_1", name="secondary4")
            output = LocalPipe("float32_5", name="output")
            args = argparse.Namespace(primary="primary", pipes="unset")
            # seed the input data
            primary.write_nowait(primary_data)
            secondary1.write_nowait(secondary1_data)
            secondary2.write_nowait(secondary2_data)
            secondary3.write_nowait(secondary3_data)
            secondary4.write_nowait(secondary4_data)
            [await pipe.close() for pipe in [primary, secondary1, secondary2, secondary3, secondary4]]
            # run filter in an event loop
            await my_filter.run(args,
                                inputs={'primary': primary,
                                        'secondary1': secondary1,
                                        'secondary2': secondary2,
                                        'secondary3': secondary3,
                                        'secondary4': secondary4},
                                outputs={'output': output})
            return await output.read_all()

        result = asyncio.run(run())
        ts = result['timestamp']
        # check that the timestamps cover the correct range
        self.assertGreaterEqual(ts[0], 200)
        self.assertLessEqual(ts[-1], 756)

        # check the primary
        primary_actual = result['data'][:, 0]
        residual = (10 * ts - 212) - primary_actual
        np.testing.assert_allclose(residual, 0)
        # check secondary1
        secondary1_actual = result['data'][:, 1]
        residual = (-3 * ts + 436) - secondary1_actual
        np.testing.assert_allclose(residual, 0)
        # check secondary2
        secondary2_actual = result['data'][:, 2]
        residual = (0.5 * ts + 101) - secondary2_actual
        np.testing.assert_allclose(residual, 0)
        # check secondary3
        secondary3_actual = result['data'][:, 3]
        residual = (8 * ts - 3000) - secondary3_actual
        np.testing.assert_allclose(residual, 0)

        if VISUALIZE:
            from matplotlib import pyplot as plt
            for data in [primary_data, secondary1_data,
                         secondary2_data, secondary3_data, secondary4_data]:
                plt.plot(data[:, 0], data[:, 1], linewidth=1)

            plt.plot(result['timestamp'], result['data'], '--', linewidth=2)
            plt.show()
