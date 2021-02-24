import asyncio


def reader_factory(fd):

    async def f():
        reader = asyncio.StreamReader()
        reader_protocol = asyncio.StreamReaderProtocol(reader)
        src = open(fd, 'rb', 0)
        loop = asyncio.get_running_loop()
        (transport, _) = await loop.connect_read_pipe(
            lambda
            : reader_protocol, src)

        def close_cb():
            transport.close()

        return reader, close_cb

    return f


def writer_factory(fd):

    async def f():
        write_protocol = asyncio.StreamReaderProtocol(asyncio.StreamReader())
        dest = open(fd, 'wb', 0)
        loop = asyncio.get_running_loop()
        (transport, p) = await loop.connect_write_pipe(
            lambda: write_protocol, dest)
        writer = asyncio.StreamWriter(
            transport, write_protocol, None, loop)
        return writer

    return f
