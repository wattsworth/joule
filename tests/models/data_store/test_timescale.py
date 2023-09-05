import testing.postgresql
import numpy as np
import asyncpg
import datetime
import itertools
import tempfile
import shutil
import os
import sys
import unittest

from joule.models import DataStream, Element, pipes
from joule.models.data_store import psql_helpers
from joule.models.data_store.timescale import TimescaleStore
from tests import helpers
from tests.models.pipes.reader import QueueReader

SQL_DIR = os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src', 'joule', 'sql')


class TestTimescale(unittest.IsolatedAsyncioTestCase):
    use_default_loop = False
    forbid_get_event_loop = True

    async def asyncSetUp(self):
        # set up the pscql database
        self.psql_dir = tempfile.TemporaryDirectory()
        self.postgresql = testing.postgresql.Postgresql(base_dir=self.psql_dir.name)
        self.postgresql.stop()
        # now that the directory structure is created, customize the *.conf file
        src = os.path.join(os.path.dirname(__file__), "postgresql.conf")
        dest = os.path.join(self.psql_dir.name, "data", "postgresql.conf")
        shutil.copyfile(src, dest)
        # restart the database
        self.postgresql = testing.postgresql.Postgresql(base_dir=self.psql_dir.name)

        self.db_url = self.postgresql.url()
        # self.db_url = "postgresql://joule:joule@127.0.0.1:5432/joule"
        conn: asyncpg.Connection = await asyncpg.connect(self.db_url)
        await conn.execute("CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE ")
        await conn.execute("CREATE USER joule_module")
        # load custom functions
        for file in os.listdir(SQL_DIR):
            file_path = os.path.join(SQL_DIR, file)
            with open(file_path, 'r') as f:
                await conn.execute(f.read())
        # await conn.execute("GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO joule_module;")
        # await conn.execute("DROP SCHEMA IF EXISTS data CASCADE")
        # await conn.execute("CREATE SCHEMA data")
        # await conn.execute("GRANT ALL ON SCHEMA data TO public")
        await conn.close()

    async def asyncTearDown(self):
        self.postgresql.stop()
        self.psql_dir.cleanup()

    async def test_runner(self):
        tests = [self._test_basic_insert_extract,
                 self._test_extract_data_with_intervals,
                 self._test_extract_decimated_data,
                 self._test_db_info,
                 self._test_info,
                 self._test_intervals,
                 self._test_remove,
                 self._test_destroy,
                 self._test_row_count,
                 self._test_actions_on_empty_streams,
                 self._test_consolidate,
                 self._test_consolidate_with_time_bounds,
                 self._test_remove_decimations,
                 self._test_redecimates_data]
        for test in tests:
            conn: asyncpg.Connection = await asyncpg.connect(self.db_url)
            await conn.execute("DROP SCHEMA IF EXISTS data CASCADE")
            await conn.execute("CREATE SCHEMA data")
            await conn.execute("GRANT ALL ON SCHEMA data TO public")

            self.store = TimescaleStore(self.db_url, 0, 60,)
            await self.store.initialize([])
            # make a sample stream with data
            self.test_stream = DataStream(id=100, name="stream1", datatype=DataStream.DATATYPE.FLOAT32,
                                          keep_us=DataStream.KEEP_ALL, decimate=True,
                                          elements=[Element(name="e%d" % x) for x in range(3)])
            pipe = pipes.LocalPipe(self.test_stream.layout)
            self.test_data = helpers.create_data(layout=self.test_stream.layout, length=1005)
            task = self.store.spawn_inserter(self.test_stream, pipe)
            await pipe.write(self.test_data)
            await pipe.close()
            runner = await task
            await runner
            await conn.close()
            # await self.store.initialize([])
            await test()
            # simulate the nose2 test output
            sys.stdout.write('o')
            await self.store.close()
            sys.stdout.flush()

    async def _test_basic_insert_extract(self):
        stream_id = 990
        self.store.extract_block_size = 500
        psql_types = ['double precision', 'real', 'bigint', 'integer', 'smallint']
        datatypes = [DataStream.DATATYPE.FLOAT64, DataStream.DATATYPE.FLOAT32, DataStream.DATATYPE.INT64,
                     DataStream.DATATYPE.INT32, DataStream.DATATYPE.INT16]
        conn: asyncpg.Connection = await asyncpg.connect(self.db_url)
        for i in range(len(datatypes)):
            datatype = datatypes[i]
            psql_type = psql_types[i]
            for n_elements in range(1, 5):
                test_stream = DataStream(id=stream_id, name="stream1", datatype=datatype, keep_us=DataStream.KEEP_ALL,
                                         elements=[Element(name="e%d" % x) for x in range(n_elements)])
                test_stream.decimate = True
                source = QueueReader()
                pipe = pipes.InputPipe(stream=test_stream, reader=source)
                nrows = 955
                data = helpers.create_data(layout=test_stream.layout, length=nrows)
                task = await self.store.spawn_inserter(test_stream, pipe)
                for chunk in helpers.to_chunks(data, 300):
                    await source.put(chunk.tobytes())
                await task

                # make sure the correct tables have been created
                records = await conn.fetch('''SELECT table_name FROM information_schema.tables 
                                                    WHERE table_schema='data';''')
                tables = list(itertools.chain(*records))
                for table in ['stream%d' % stream_id, 'stream%d_intervals' % stream_id]:
                    self.assertIn(table, tables)

                # check the column data types
                records = await conn.fetch('''SELECT column_name, data_type FROM information_schema.columns 
                                                            WHERE table_name='stream%d' AND table_schema='data';''' % stream_id)
                (names, types) = zip(*records)
                expected_elements = ['time'] + ['elem%d' % x for x in range(n_elements)]
                self.assertCountEqual(names, expected_elements)
                expected_psql_types = tuple(['timestamp without time zone'] + [psql_type for x in range(n_elements)])
                self.assertEqual(types, expected_psql_types)
                self.assertEqual(len(records), n_elements + 1)

                # extract raw data
                extracted_data = []

                async def callback(rx_data, layout, factor):
                    self.assertEqual(layout, test_stream.layout)
                    self.assertEqual(factor, 1)
                    extracted_data.append(rx_data)

                await self.store.extract(test_stream, start=None, end=None, callback=callback)
                extracted_data = np.hstack(extracted_data)
                np.testing.assert_array_equal(extracted_data, data)

                level = 64
                data_mean = np.mean(extracted_data['data'][:level], axis=0)
                data_max = np.max(extracted_data['data'][:level], axis=0)
                data_min = np.min(extracted_data['data'][:level], axis=0)

                # extract decimated data
                async def d_callback(rx_data, layout, factor):
                    self.assertEqual(layout, test_stream.decimated_layout)
                    self.assertEqual(factor, level)
                    extracted_data.append(rx_data)

                extracted_data = []
                await self.store.extract(test_stream, decimation_level=level,
                                         start=None, end=None, callback=d_callback)
                extracted_data = np.hstack(extracted_data)
                expected = np.hstack((data_mean, data_min, data_max))
                np.testing.assert_array_almost_equal(expected, extracted_data['data'][0])
                stream_id += 1
        await conn.close()

    async def _test_extract_data_with_intervals(self):
        test_stream = DataStream(id=1, name="stream1", datatype=DataStream.DATATYPE.FLOAT32, keep_us=DataStream.KEEP_ALL,
                                 decimate=True, elements=[Element(name="e%d" % x) for x in range(3)])
        pipe = pipes.LocalPipe(test_stream.layout)
        nrows = 955
        data = helpers.create_data(layout=test_stream.layout, length=nrows)
        task = await self.store.spawn_inserter(test_stream, pipe)
        for chunk in helpers.to_chunks(data, 300):
            await pipe.write(chunk)
            await pipe.close_interval()
        await pipe.close()
        await task

        # extract data
        extracted_data = []

        async def callback(rx_data, layout, factor):
            self.assertEqual(layout, test_stream.layout)
            self.assertEqual(factor, 1)
            extracted_data.append(rx_data)

        await self.store.extract(test_stream, start=None, end=None, callback=callback)
        extracted_data = np.hstack(extracted_data)
        # check for interval boundaries
        np.testing.assert_array_equal(extracted_data[300], pipes.interval_token(test_stream.layout))
        np.testing.assert_array_equal(extracted_data[601], pipes.interval_token(test_stream.layout))
        np.testing.assert_array_equal(extracted_data[902], pipes.interval_token(test_stream.layout))

    async def _test_extract_decimated_data(self):

        extracted_data = []

        async def callback(rx_data, layout, factor):
            self.assertEqual(layout, self.test_stream.decimated_layout)
            self.assertEqual(factor, 4)
            extracted_data.append(rx_data)

        await self.store.extract(self.test_stream, max_rows=16,
                                 start=self.test_data['timestamp'][66],
                                 end=self.test_data['timestamp'][64 + 4 * 16],
                                 callback=callback)
        extracted_data = np.hstack(extracted_data)
        self.assertLessEqual(len(extracted_data), 16)
        self.assertGreater(len(extracted_data), 4)

    async def _test_remove_decimations(self):

        # make sure the stream is decimated:
        conn: asyncpg.Connection = await asyncpg.connect(self.db_url)
        table_names = await psql_helpers.get_decimation_table_names(conn, self.test_stream, with_schema=False)
        for table in [f'stream100_{4**i}' for i in range(1,6)]:
           self.assertIn(table, table_names)
        await self.store.drop_decimations(self.test_stream)
        # drop the decimations
        table_names = await psql_helpers.get_decimation_table_names(conn, self.test_stream, with_schema=False)
        # make sure the tables are dropped
        self.assertEqual(len(table_names), 0)
        await conn.close()

    async def _test_redecimates_data(self):
        # create decimated data
        test_stream = DataStream(id=1, name="stream1", datatype=DataStream.DATATYPE.FLOAT32,
                                 keep_us=DataStream.KEEP_ALL,
                                 elements=[Element(name="e%d" % x) for x in range(3)])
        test_stream.decimate = True
        source = QueueReader()
        pipe = pipes.InputPipe(stream=test_stream, reader=source)
        nrows = 1024
        data = helpers.create_data(layout=test_stream.layout, length=nrows)
        task = await self.store.spawn_inserter(test_stream, pipe)
        for chunk in helpers.to_chunks(data, 16):
            await source.put(chunk.tobytes())
            await source.put(pipes.interval_token(test_stream.layout).tobytes())
        await task
        conn: asyncpg.Connection = await asyncpg.connect(self.db_url)
        table_names = await psql_helpers.get_decimation_table_names(conn, test_stream, with_schema=False)
        # interval breaks cause decimation to stop after level 16 (level 64 is created but empty)
        self.assertEqual(len(table_names),3)
        orig_data = await conn.fetch("SELECT * FROM data.stream1_16")

        # redecimate doesn't change anything
        await self.store.decimate(test_stream)
        redecimated_data = await conn.fetch("SELECT * FROM data.stream1_16")
        self.assertEqual(orig_data, redecimated_data)

        # now consolidate the intervals
        await self.store.consolidate(test_stream, start=None, end=None,
                                     max_gap = data['timestamp'][1]-data['timestamp'][0])
        # redecimate
        await self.store.decimate(test_stream)
        table_names = await psql_helpers.get_decimation_table_names(conn, test_stream, with_schema=False)
        for table in [f'stream1_{4**i}' for i in range(1,6)]:
           self.assertIn(table, table_names)
        await conn.close()

    async def _test_nondecimating_inserter(self):
        # TODO
        pass

    async def _test_row_count(self):
        test_data = helpers.create_data(layout=self.test_stream.layout, length=10000)
        test_stream = DataStream(id=95, name="stream1", datatype=DataStream.DATATYPE.FLOAT32, keep_us=DataStream.KEEP_ALL,
                                 decimate=True, elements=[Element(name="e%d" % x) for x in range(3)])
        pipe = pipes.LocalPipe(test_stream.layout)
        task = await self.store.spawn_inserter(test_stream, pipe)
        await pipe.write(test_data)
        await pipe.close()
        await task
        conn: asyncpg.Connection = await asyncpg.connect(self.db_url)
        # test to make sure nrows is within 10% of actual value
        # Test: [start, end]
        nrows = await psql_helpers.get_row_count(conn, test_stream,
                                                 None,
                                                 None)
        self.assertGreater(nrows, len(test_data) * 0.9)
        # Test: [ts,end]
        nrows = await psql_helpers.get_row_count(conn, test_stream, test_data[len(test_data) // 2][0], None)
        self.assertLess(abs(nrows - len(test_data) // 2), 0.1 * len(test_data))
        # Test: [start, ts]
        nrows = await psql_helpers.get_row_count(conn, test_stream,
                                                 None,
                                                 test_data[len(test_data) // 3][0])
        self.assertLess(abs(nrows - len(test_data) // 3), 0.1 * len(test_data))

        # Test: [ts, ts]
        nrows = await psql_helpers.get_row_count(conn, test_stream,
                                                 test_data[2 * len(test_data) // 6][0],
                                                 test_data[3 * len(test_data) // 6][0])
        self.assertLess(abs(nrows - len(test_data) // 6), 0.1 * len(test_data))

        # Test: [ts, ts] (no data)
        nrows = await psql_helpers.get_row_count(conn, test_stream,
                                                 test_data['timestamp'][0] - 100,
                                                 test_data['timestamp'][0] - 50)
        self.assertEqual(0, nrows)

        # Test row count for stream with no data tables
        empty_stream = DataStream(id=96, name="empty", datatype=DataStream.DATATYPE.FLOAT64,
                                  keep_us=100, decimate=True, elements=[Element(name="e%d" % x) for x in range(8)])
        nrows = await psql_helpers.get_row_count(conn, empty_stream,
                                                 None,
                                                 None)
        self.assertEqual(0, nrows)
        nrows = await psql_helpers.get_row_count(conn, empty_stream,
                                                 test_data[len(test_data) // 2][0],
                                                 None)
        self.assertEqual(0, nrows)
        nrows = await psql_helpers.get_row_count(conn, test_stream,
                                                 test_data['timestamp'][0] - 100,
                                                 test_data['timestamp'][0] - 50)
        self.assertEqual(0, nrows)
        await conn.close()

    async def _test_remove(self):

        #  XXXXXXX------XXXXXXX
        #        ^|     ^
        # remove a chunk of data from the middle
        await self.store.remove(self.test_stream,
                                self.test_data['timestamp'][300],
                                self.test_data['timestamp'][400])
        # XXXXXXX------===XXXX
        #       ^|        ^
        # remove another chunk
        await self.store.remove(self.test_stream,
                                self.test_data['timestamp'][350],
                                self.test_data['timestamp'][500])

        # XXX___----===XXX
        #   ^|         ^
        await self.store.remove(self.test_stream,
                                self.test_data['timestamp'][250],
                                self.test_data['timestamp'][300])

        # extract the data, should have an interval gap between 249 and 500
        # and a *single* interval boundary at 250

        extracted_data = []

        async def callback(rx_data, layout, decimated):
            extracted_data.append(rx_data)

        await self.store.extract(self.test_stream, start=None, end=None,
                                 callback=callback)
        extracted_data = np.hstack(extracted_data)

        # beginning is unchanged
        np.testing.assert_array_equal(extracted_data[:249], self.test_data[:249])
        # interval boundary marking missing data
        np.testing.assert_array_equal(extracted_data[250],
                                      pipes.interval_token(self.test_stream.layout))
        # end is unchanged (closing interval boundary ignored)
        np.testing.assert_array_equal(extracted_data[251:], self.test_data[500:])

        # two intervals of data
        intervals = await self.store.intervals(self.test_stream, start=None, end=None)
        ts = self.test_data['timestamp']
        expected = [[ts[0], ts[249] + 1],
                    [ts[500], ts[-1] + 1]]
        self.assertEqual(intervals, expected)

    async def _test_destroy(self):
        await self.store.destroy(self.test_stream)
        records = await self.store.info([self.test_stream])
        info = records[self.test_stream.id]
        self.assertEqual(info.start, None)
        self.assertEqual(info.end, None)
        self.assertEqual(info.total_time, 0)
        self.assertEqual(info.rows, 0)
        self.assertEqual(info.bytes, 0)

    async def _test_intervals(self):

        ts = self.test_data['timestamp']

        async def _insert_boundary(_conn, _ts: int):
            dt = datetime.datetime.fromtimestamp(_ts / 1e6, tz=datetime.timezone.utc)
            query = "INSERT INTO data.stream100_intervals (time) VALUES ('%s')" % dt
            await _conn.execute(query)

        conn: asyncpg.Connection = await asyncpg.connect(self.db_url)

        # XXXX|XXXXX|XXXXX
        await _insert_boundary(conn, ts[99] + 1)
        await _insert_boundary(conn, ts[199] + 1)
        expected = [[ts[0], ts[99] + 1],
                    [ts[100], ts[199] + 1],
                    [ts[200], ts[-1] + 1]]
        intervals = await self.store.intervals(self.test_stream, None, None)
        self.assertEqual(expected, intervals)

        # insert an extra boundary that does not create a new interval
        # XXXX||XXXXX|XXXXX
        await _insert_boundary(conn, ts[99] + 10)

        intervals = await self.store.intervals(self.test_stream, None, None)
        self.assertEqual(expected, intervals)

        # insert boundaries at the beginning and end of the data,
        # this should also not create any new intervals
        # |XXXX||XXXXX|XXXXX|

        await _insert_boundary(conn, ts[0] - 1)
        await _insert_boundary(conn, ts[-1] + 1)
        intervals = await self.store.intervals(self.test_stream, None, None)
        self.assertEqual(expected, intervals)

        # insert an actual boundary, this should create a new interval
        # |XXXX||XXXXX|XXX|X|
        await _insert_boundary(conn, ts[780] + 1)
        intervals = await self.store.intervals(self.test_stream, None, None)
        expected = [[ts[0], ts[99] + 1],
                    [ts[100], ts[199] + 1],
                    [ts[200], ts[780] + 1],
                    [ts[781], ts[-1] + 1]]
        self.assertEqual(expected, intervals)
        await conn.close()

    async def _test_consolidate(self):
        # intervals less than max_gap us apart are consolidated
        # data: 100 samples spaced at 1000us
        test_stream = DataStream(id=1, name="stream1", datatype=DataStream.DATATYPE.FLOAT32, keep_us=DataStream.KEEP_ALL,
                                 decimate=True, elements=[Element(name="e%d" % x) for x in range(3)])
        pipe = pipes.LocalPipe(test_stream.layout)
        nrows = 955
        orig_data = helpers.create_data(layout=test_stream.layout, length=nrows)
        chunks = [orig_data[:300], orig_data[305:400], orig_data[402:700], orig_data[800:]]
        # data: |++++++|  |+++++++++|    |++++++|    |++++|
        #               ^--5000 us    ^--2000 us   ^---0.1 sec (retained)
        chunks = [orig_data[:300], orig_data[305:400], orig_data[402:700], orig_data[800:850], orig_data[852:]]
        # data: |++++++|  |+++++++++|    |++++++|    |++++|  |++++|
        #               ^--5000 us    ^--2000 us   |        ^--- 2000 us
        #                                          `---0.1 sec (retained)
        task = await self.store.spawn_inserter(test_stream, pipe)
        for chunk in chunks:
            await pipe.write(chunk)
            await pipe.close_interval()
        await pipe.close()
        await task

        # extract data
        extracted_data = []

        rx_chunks = []

        async def callback(rx_data, layout, factor):
            if rx_data[0] != pipes.interval_token(layout):
                rx_chunks.append(rx_data)

        await self.store.consolidate(test_stream, start=None, end=None, max_gap=6e3)
        await self.store.extract(test_stream, start=None, end=None, callback=callback)

        # should only be two intervals left (the first two are consolidated)
        np.testing.assert_array_equal(rx_chunks[0], np.hstack(chunks[:3]))
        np.testing.assert_array_equal(rx_chunks[1], np.hstack(chunks[3:]))
        self.assertEqual(len(rx_chunks), 2)

    async def _test_consolidate_with_time_bounds(self):
        # intervals less than max_gap us apart between start and end are consolidated
        # data: 100 samples spaced at 1000us
        test_stream = DataStream(id=1, name="stream1", datatype=DataStream.DATATYPE.FLOAT32, keep_us=DataStream.KEEP_ALL,
                                 decimate=True, elements=[Element(name="e%d" % x) for x in range(3)])
        pipe = pipes.LocalPipe(test_stream.layout)
        nrows = 955
        orig_data = helpers.create_data(layout=test_stream.layout, length=nrows)
        chunks = [orig_data[:300], orig_data[305:400], orig_data[402:700], orig_data[800:850],orig_data[852:]]
        # data: |++++++|  |+++++++++|    |++++++|    |++++|  |++++|
        #               ^--(retained) ^--2000 us   |        ^--- 2000 us (retained)
        #                                          `---0.1 sec (retained)
        task = await self.store.spawn_inserter(test_stream, pipe)
        for chunk in chunks:
            await pipe.write(chunk)
            await pipe.close_interval()
        await pipe.close()
        await task

        # extract data
        extracted_data = []

        rx_chunks = []

        async def callback(rx_data, layout, factor):
            if rx_data[0] != pipes.interval_token(layout):
                rx_chunks.append(rx_data)

        await self.store.consolidate(test_stream, start=chunks[1][3]['timestamp'],
                                     end=chunks[3][3]['timestamp'], max_gap=6e3)
        await self.store.extract(test_stream, start=None, end=None, callback=callback)

        # should only be four intervals left (the inner short intervals are consolidated)
        np.testing.assert_array_equal(rx_chunks[0], chunks[0])
        np.testing.assert_array_equal(rx_chunks[1], np.hstack(chunks[1:3]))
        np.testing.assert_array_equal(rx_chunks[2], chunks[3])
        np.testing.assert_array_equal(rx_chunks[3], chunks[4])

        self.assertEqual(len(rx_chunks), 4)

    async def _test_db_info(self):
        db_info = await self.store.dbinfo()
        self.assertTrue(os.path.isdir(db_info.path))
        self.assertGreater(db_info.other, 0)
        self.assertGreater(db_info.reserved, 0)
        self.assertGreater(db_info.free, 0)
        self.assertGreater(db_info.size, 0)

    async def _test_info(self):
        # create another stream
        empty_stream = DataStream(id=103, name="empty stream", datatype=DataStream.DATATYPE.INT32,
                                  keep_us=DataStream.KEEP_ALL, decimate=True,
                                  elements=[Element(name="e%d" % x) for x in range(8)])
        stream2 = DataStream(id=104, name="stream2", datatype=DataStream.DATATYPE.INT32,
                             keep_us=DataStream.KEEP_ALL, decimate=True,
                             elements=[Element(name="e%d" % x) for x in range(8)])
        pipe = pipes.LocalPipe(stream2.layout)
        test_data = helpers.create_data(layout=stream2.layout, length=800)
        task = await self.store.spawn_inserter(stream2, pipe)
        await pipe.write(test_data)
        await pipe.close()
        await task
        records = await self.store.info([self.test_stream, stream2, empty_stream])
        # check stream1
        info = records[self.test_stream.id]
        self.assertEqual(info.start, self.test_data['timestamp'][0])
        self.assertEqual(info.end, self.test_data['timestamp'][-1])
        self.assertEqual(info.total_time, info.end - info.start)
        # rows are approximate
        self.assertLess(abs(len(self.test_data) - info.rows), len(self.test_data) * 0.1)
        self.assertGreater(info.bytes, 0)

        # check stream2
        info = records[stream2.id]
        self.assertEqual(info.start, test_data['timestamp'][0])
        self.assertEqual(info.end, test_data['timestamp'][-1])
        self.assertEqual(info.total_time, info.end - info.start)
        self.assertLess(abs(len(test_data) - info.rows), len(test_data) * 0.1)
        self.assertGreater(info.bytes, 0)

        # check the empty stream
        info = records[empty_stream.id]
        self.assertEqual(info.start, None)
        self.assertEqual(info.end, None)
        self.assertEqual(info.total_time, 0)
        self.assertEqual(info.rows, 0)
        self.assertEqual(info.bytes, 0)

    async def _test_actions_on_empty_streams(self):
        # make sure all actions can be performed on streams with no data
        empty_stream = DataStream(id=103, name="empty stream", datatype=DataStream.DATATYPE.INT32,
                                  keep_us=DataStream.KEEP_ALL, decimate=True,
                                  elements=[Element(name="e%d" % x) for x in range(8)])

        # ==== extract =====
        cb_executed = False
        cb_layout = None
        cb_factor = None

        async def callback(rx_data, layout, factor):
            nonlocal cb_executed, cb_layout, cb_factor
            cb_executed = True
            self.assertEqual(len(rx_data), 0)
            cb_layout = layout
            cb_factor = factor

        # stream with no data tables
        await self.store.extract(empty_stream, start=None, end=None, callback=callback)
        self.assertTrue(cb_executed)
        self.assertEqual(cb_layout, empty_stream.layout)
        self.assertEqual(cb_factor, 1)
        cb_executed = False
        await self.store.extract(empty_stream, start=100, end=None, callback=callback)
        self.assertTrue(cb_executed)
        self.assertEqual(cb_layout, empty_stream.layout)
        self.assertEqual(cb_factor, 1)
        cb_executed = False
        await self.store.extract(empty_stream, start=100, end=300, callback=callback)
        self.assertTrue(cb_executed)
        self.assertEqual(cb_layout, empty_stream.layout)
        self.assertEqual(cb_factor, 1)
        cb_executed = False
        await self.store.extract(empty_stream, start=None, end=100, callback=callback)
        self.assertTrue(cb_executed)
        self.assertEqual(cb_layout, empty_stream.layout)
        self.assertEqual(cb_factor, 1)
        cb_executed = False
        await self.store.extract(empty_stream, start=100, end=300, max_rows=40, callback=callback)
        self.assertTrue(cb_executed)
        self.assertEqual(cb_layout, empty_stream.layout)
        self.assertEqual(cb_factor, 1)
        cb_executed = False
        await self.store.extract(empty_stream, start=100, end=300, decimation_level=40, callback=callback)
        self.assertTrue(cb_executed)
        self.assertEqual(cb_layout, empty_stream.decimated_layout)
        self.assertEqual(cb_factor, 40)

        # non-existent decimation level
        await self.store.extract(self.test_stream, start=None, end=None, decimation_level=97,
                                 callback=callback)

        #  ==== intervals ====
        intervals = await self.store.intervals(empty_stream, None, None)
        self.assertEqual(0, len(intervals))
        intervals = await self.store.intervals(empty_stream, 100, None)
        self.assertEqual(0, len(intervals))
        intervals = await self.store.intervals(empty_stream, None, 100)
        self.assertEqual(0, len(intervals))
        intervals = await self.store.intervals(empty_stream, 100, 300)
        self.assertEqual(0, len(intervals))

        #  ==== remove ====
        await self.store.remove(empty_stream, None, None)
        await self.store.remove(empty_stream, 100, None)
        await self.store.remove(empty_stream, None, 100)
        await self.store.remove(empty_stream, 100, 300)

        # ==== destroy ====
        await self.store.destroy(empty_stream)
