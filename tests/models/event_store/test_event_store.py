import asynctest
import testing.postgresql
import asyncpg
import tempfile
import shutil
import os
import sys

from joule.models.data_store.event_store import EventStore
from joule.models.event_stream import EventStream


class TestEventStore(asynctest.TestCase):
    use_default_loop = False
    forbid_get_event_loop = True

    async def setUp(self):
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

        await conn.close()

    async def tearDown(self):
        self.postgresql.stop()
        self.psql_dir.cleanup()

    async def test_runner(self):
        tests = [self._test_basic_insert_extract_remove,
                 self._test_time_bound_queries,
                 self._test_remove_bound_queries]
        for test in tests:
            conn: asyncpg.Connection = await asyncpg.connect(self.db_url)
            await conn.execute("DROP SCHEMA IF EXISTS data CASCADE")
            await conn.execute("CREATE SCHEMA data")
            await conn.execute("GRANT ALL ON SCHEMA data TO public")

            self.store = EventStore(self.db_url)
            await self.store.initialize()
            await conn.close()
            await test()
            # simulate the nose2 test output
            sys.stdout.write('o')
            await self.store.close()
            sys.stdout.flush()

    async def _test_basic_insert_extract_remove(self):
        event_stream1 = EventStream(id=1, name='test_stream1')
        events1 = [{'start_time': i * 100,
                    'end_time': i * 100 + 10,
                    'content': {'title': "Event%d" % i,
                                'stream': event_stream1.name}
                    } for i in range(20)]
        await self.store.insert(event_stream1, events1)
        event_stream2 = EventStream(id=2, name='test_stream2')
        events2 = [{'start_time': (i * 100) + 3,
                    'end_time': (i * 100) + 13,
                    'content': {'title': "Event%d" % i,
                                'stream': event_stream2.name}
                    } for i in range(20)]
        await self.store.insert(event_stream2, events2)
        # now try to read them back
        rx_events = await self.store.extract(event_stream1)
        self.assertListEqual(events1, rx_events)
        # ...the two event streams are independent
        rx_events = await self.store.extract(event_stream2)
        self.assertListEqual(events2, rx_events)
        # now remove them
        await self.store.remove(event_stream1)
        rx_events = await self.store.extract(event_stream1)
        self.assertListEqual(rx_events, [])
        # ...the two event streams are independent
        rx_events = await self.store.extract(event_stream2)
        self.assertListEqual(events2, rx_events)

    async def _test_time_bound_queries(self):
        event_stream1 = EventStream(id=1, name='test_stream1')
        early_events = [{'start_time': i * 100,
                         'end_time': i * 100 + 10,
                         'content': {'title': "Event%d" % i,
                                     'stream': event_stream1.name}
                         } for i in range(20)]
        mid_events = [{'start_time': i * 100,
                       'end_time': i * 100 + 10,
                       'content': {'title': "Event%d" % i,
                                   'stream': event_stream1.name}
                       } for i in range(30, 40)]
        late_events = [{'start_time': i * 100,
                        'end_time': i * 100 + 10,
                        'content': {'title': "Event%d" % i,
                                    'stream': event_stream1.name}
                        } for i in range(50, 60)]
        await self.store.insert(event_stream1, early_events + mid_events + late_events)

        # now try to read them back
        rx_events = await self.store.extract(event_stream1, start=3000, end=4500)
        self.assertListEqual(rx_events, mid_events)
        rx_events = await self.store.extract(event_stream1, end=4500)
        self.assertListEqual(rx_events, early_events + mid_events)
        rx_events = await self.store.extract(event_stream1, start=3000)
        self.assertListEqual(rx_events, mid_events + late_events)

    async def _test_remove_bound_queries(self):
        event_stream1 = EventStream(id=20, name='test_stream1')

        early_events = [{'start_time': i * 100,
                         'end_time': i * 100 + 10,
                         'content': {'title': "Event%d" % i,
                                     'stream': event_stream1.name}
                         } for i in range(20)]
        mid_events = [{'start_time': i * 100,
                       'end_time': i * 100 + 10,
                       'content': {'title': "Event%d" % i,
                                   'stream': event_stream1.name}
                       } for i in range(30, 40)]
        late_events = [{'start_time': i * 100,
                        'end_time': i * 100 + 10,
                        'content': {'title': "Event%d" % i,
                                    'stream': event_stream1.name}
                        } for i in range(50, 60)]
        await self.store.insert(event_stream1, early_events + mid_events + late_events)


        # remove the middle
        await self.store.remove(event_stream1, start=3000, end=4500)
        rx_events = await self.store.extract(event_stream1)
        self.assertListEqual(rx_events, early_events+late_events)
        # remove the beginning
        await self.store.remove(event_stream1, end=3000)
        rx_events = await self.store.extract(event_stream1)
        self.assertListEqual(rx_events, late_events)
        # remove the end
        await self.store.remove(event_stream1, start=4500)
        rx_events = await self.store.extract(event_stream1)
        self.assertListEqual(rx_events, [])


