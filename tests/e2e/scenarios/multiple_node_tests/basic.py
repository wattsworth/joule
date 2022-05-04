import asynctest

import joule.api
from joule import api, errors


class TestBasicAPI(asynctest.TestCase):

    async def setUp(self):
        self.node1 = api.get_node("node1.joule")
        followers = await self.node1.follower_list()
        self.assertEqual(len(followers), 1)
        self.node2 = followers[0]

        """
        node1.joule:
        /main/folder/added:int32[x]
        node2.joule:
        /main/folder/base:int32[x]
        """

    async def tearDown(self):
        await self.node1.close()
        await self.node2.close()

    async def test_retrieves_streams(self):
        logs = await self.node1.module_logs("Remote")
        print(logs)
        print('----------')
        added_stream = await self.node1.data_stream_get("/main/folder/added")
        base_stream = await self.node2.data_stream_get("/main/folder/base")
        # make sure added_stream has data
        added_data = await self.node1.data_subscribe(added_stream)
        base_data = await self.node2.data_subscribe(base_stream)
        base_block = await base_data.read()
        added_block = await added_data.read()
        # align the time stamps
        diff = base_block['timestamp'][0] - added_block['timestamp'][0]
        print("the diff is %d" % diff)
        await added_data.close()
        await base_data.close()

    async def test_copies_events(self):
        events = []
        for i in range(1000, 2000, 100):
            events.append(joule.api.Event(start_time=i, end_time=i + 50,
                                          content={'name': f"Event{i}"}))
        event_stream = joule.api.EventStream("Test Events")
        await self.node1.event_stream_create(event_stream, "/event streams")
        await self.node1.event_stream_write(event_stream, events)




