from joule.models.pipes import Pipe


class OutputPipe(Pipe):

    def __init__(self, name=None, stream=None,
                 writer=None, writer_factory=None, fd=None):
        super().__init__(name=name, stream=stream,
                         direction=Pipe.DIRECTION.OUTPUT)
        self.writer_factory = writer_factory
        self.writer = writer
        # read fd to send to a consumer process
        # should be marked as inheritable to surrive fork
        self.fd = fd

    async def write(self, data):
        if self.writer is None:
            self.writer = await self.writer_factory()

        # make sure dtype is structured
        sdata = self._apply_dtype(data)
        self.writer.write(sdata.tostring())
        await self.writer.drain()

    def close(self):
        if self.writer is not None:
            self.writer.close()
            self.writer = None

