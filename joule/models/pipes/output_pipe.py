import asyncio
from joule.models.pipes import Pipe, interval_token


class OutputPipe(Pipe):

    def __init__(self, name=None, stream=None, layout=None,
                 writer: asyncio.StreamWriter=None, writer_factory=None):
        super().__init__(name=name, stream=stream, layout=layout,
                         direction=Pipe.DIRECTION.OUTPUT)
        self.writer_factory = writer_factory
        self.writer: asyncio.StreamWriter = writer

    async def write(self, data):
        if self.writer is None:
            self.writer = await self.writer_factory()
        # make sure dtype is structured
        sdata = self._apply_dtype(data)
        self.writer.write(sdata.tostring())
        await self.writer.drain()

    async def close_interval(self):
        self.writer.write(interval_token(self.layout).tostring())
        await self.writer.drain()

    async def close(self):
        if self.writer is not None:
            self.writer.close()
            # TODO: available in python3.7
            # await self.writer.wait_closed()
            # Hack to close the transport
            await asyncio.sleep(0.01)
            self.writer = None
