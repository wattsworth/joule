import asyncio


def reader_factory(fd, loop=None):
    if(loop is None):
        loop = asyncio.get_event_loop()

    async def f():
        reader = asyncio.StreamReader()
        reader_protocol = asyncio.StreamReaderProtocol(reader)
        f = open(fd, 'rb')
        (transport, _) = await loop.connect_read_pipe(
            lambda: reader_protocol, f)
        return reader
    
    return f


def writer_factory(fd, loop=None):
    if(loop is None):
        loop = asyncio.get_event_loop()

    async def f():
        write_protocol = asyncio.StreamReaderProtocol(asyncio.StreamReader())
        f = open(fd, 'wb')
        (transport, _) = await loop.connect_write_pipe(
            lambda: write_protocol, f)
        writer = asyncio.StreamWriter(
           transport, write_protocol, None, loop)
        return writer

    return f
