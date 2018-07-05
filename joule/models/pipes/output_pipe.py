from joule.models.pipes import Pipe, interval_token


class OutputPipe(Pipe):

    def __init__(self, name=None, stream=None, layout=None,
                 writer=None, writer_factory=None):
        super().__init__(name=name, stream=stream, layout=layout,
                         direction=Pipe.DIRECTION.OUTPUT)
        self.writer_factory = writer_factory
        self.writer = writer

    async def write(self, data):
        if self.writer is None:
            self.writer = await self.writer_factory()
        # make sure dtype is structured
        sdata = self._apply_dtype(data)
        self.writer.write(sdata.tostring())
        await self.writer.drain()

    async def close_interval(self):
        self.writer.write(interval_token(self.layout))
        await self.writer.drain()

    def close(self):
        if self.writer is not None:
            self.writer.close()
            self.writer = None
