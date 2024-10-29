import unittest
import json
from joule import api, errors
from joule.utilities import human_to_timestamp as h2ts
from joule.utilities import timestamp_to_human as ts2h

t1 = h2ts('1 Sep 2020 00:00:00')
t2 = h2ts('2 Sep 2020 00:00:00')
t3 = h2ts('3 Sep 2020 00:00:00')
t4 = h2ts('4 Sep 2020 00:00:00')
t5 = h2ts('5 Sep 2020 00:00:00')
t6 = h2ts('6 Sep 2020 00:00:00')
t7 = h2ts('7 Sep 2020 00:00:00')
t8 = h2ts('8 Sep 2020 00:00:00')
t9 = h2ts('9 Sep 2020 00:00:00')
tA = h2ts('10 Sep 2020 00:00:00')
tB = h2ts('11 Sep 2020 00:00:00')
tC = h2ts('12 Sep 2020 00:00:00')
tD = h2ts('13 Sep 2020 00:00:00')
tE = h2ts('14 Sep 2020 00:00:00')
tF = h2ts('15 Sep 2020 00:00:00')
TS_LIST = [t1, t2, t3, t4, t5, t6, t7, t8, t9, tA, tB, tC, tD, tE, tF]
class TestStreamMethods(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self):
        self.node = api.get_node()
        """
        └── original
            └── events
        """
        events = []
        for ts in TS_LIST:
            events.append(api.Event(start_time=ts,end_time=ts+60e6, content={"name": ts2h(ts), "value": ts}))
        event_stream = await self.node.event_stream_create(api.EventStream(name="events",event_fields={"name": "string","value": "numeric"}), "/original")
        await self.node.event_stream_write(event_stream, events)
        await self.node.close()

    async def asyncTearDown(self):
        await self.node.folder_delete("/original", recursive=True)
        await self.node.close()

    async def test_stream_move(self):
        await self.node.event_stream_move("/original/events", "/test/deeper")
        info = await self.node.event_stream_info("/test/deeper/events")
        self.assertEqual(info.event_count,15)

    async def test_stream_read(self):
        from joule.api import event_stream
        event_stream.EVENT_READ_BLOCK_SIZE = 4 # force multiple backend reads

        ## can read one at a time
        i = 0
        async for event in self.node.event_stream_read("/original/events"):
            self.assertEqual(event.start_time, TS_LIST[i])
            i += 1
        self.assertEqual(i, 15)

        ## can read in blocks
        i = 0
        async for events in self.node.event_stream_read("/original/events", block_size=5):
            self.assertEqual(len(events), 5)
            i+=5
        self.assertEqual(i, 15)

        ## can read as list
        events = await self.node.event_stream_read_list("/original/events")
        self.assertEqual(len(events), 15)

        ## too many events generates a warning
        with self.assertLogs(level='WARN'):
            events = await self.node.event_stream_read_list("/original/events", limit=10)
        self.assertEqual(len(events), 10)

        ## can read by time range
        events = await self.node.event_stream_read_list("/original/events", start=t5+1, end=tD+1, include_on_going_events=False)
        self.assertEqual(len(events), 8)
        self.assertEqual(events[0].start_time, t6)
        self.assertEqual(events[-1].start_time, tD)

        ## include on going events
        events = await self.node.event_stream_read_list("/original/events", start=t5+1, end=tD+1, include_on_going_events=True)
        self.assertEqual(len(events), 9)
        self.assertEqual(events[0].start_time, t5)
        self.assertEqual(events[-1].start_time, tD)
        
        ## can filter by content
        events = await self.node.event_stream_read_list("/original/events", json_filter=json.dumps([[['value','lte',t2]]]))
        self.assertEqual(len(events), 2)
        self.assertEqual(events[0].start_time, t1)
        self.assertEqual(events[-1].start_time, t2)

    async def test_event_delete(self):
        # can remove an interior time range
        await self.node.event_stream_remove("/original/events", start=t5, end=tD+1)
        expected_events = [t1, t2, t3, t4, tE, tF]
        events = await self.node.event_stream_read_list("/original/events")
        self.assertListEqual([e.start_time for e in events], expected_events)

        # can remove the beginning
        await self.node.event_stream_remove("/original/events", end=t2+1)
        expected_events = [t3, t4, tE, tF]
        events = await self.node.event_stream_read_list("/original/events")
        self.assertListEqual([e.start_time for e in events], expected_events)

        # can remove the end: NOTE: delete includes ongoing events
        await self.node.event_stream_remove("/original/events", start=tE+1)
        expected_events = [t3, t4]
        events = await self.node.event_stream_read_list("/original/events")
        self.assertListEqual([e.start_time for e in events], expected_events)

        # can remove by JSON filter
        await self.node.event_stream_remove("/original/events", json_filter=json.dumps([[['value','lt',t4]]]))
        expected_events = [t4]
        events = await self.node.event_stream_read_list("/original/events")
        self.assertListEqual([e.start_time for e in events], expected_events)

        # can remove all the events
        await self.node.event_stream_remove("/original/events")
        events = await self.node.event_stream_read_list("/original/events")
        self.assertEqual(len(events), 0)

        # can remove the stream itself
        await self.node.event_stream_delete("/original/events")
        with self.assertRaises(errors.ApiError):
            await self.node.event_stream_info("/original/events")

        