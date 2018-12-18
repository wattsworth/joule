import asyncio


def reader_factory(fd, loop: asyncio.AbstractEventLoop):

    async def f():
        reader = asyncio.StreamReader(loop=loop)
        reader_protocol = asyncio.StreamReaderProtocol(reader, loop=loop)
        src = open(fd, 'rb', 0)
        (transport, _) = await loop.connect_read_pipe(
            lambda
            : reader_protocol, src)

        def close_cb():
            transport.close()

        return reader, close_cb

    return f


def writer_factory(fd, loop: asyncio.AbstractEventLoop):

    async def f():
        write_protocol = asyncio.StreamReaderProtocol(asyncio.StreamReader())
        dest = open(fd, 'wb', 0)
        (transport, p) = await loop.connect_write_pipe(
            lambda: write_protocol, dest)
        writer = asyncio.StreamWriter(
            transport, write_protocol, None, loop)
        return writer

    return f
