from joule.daemon import stream
import asyncio


class Reader():
    def __init__(self, async_client, client, path, time_range, loop=None):
        self.async_client = async_client
        self.client = client
        info = client.stream_info()
        self.stream = stream.Stream(info.path, '',
                                    path, info.layout_type,
                                    0, False)
        self.queue = asyncio.Queue(loop=loop)
        
    def get_stream(self):
        return self.stream

    def get_queue(self):
        return self.queue
    
    async def run(self):
        with async_client.stream_extract(path, time_range[0], time_range[1]) as reader:
            data = await reader.read()
            await self.queue.put(data)
        self.queue.put(None)
    
