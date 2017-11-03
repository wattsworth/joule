
import traceback
import asyncio
import logging
from joule.utils.numpypipe import (
    StreamNumpyPipeReader,
    StreamNumpyPipeWriter,
    EmptyPipe)
from joule.utils import network


class Server:
    def __init__(self, subscription_factory, inserter_factory, loop=None):
        self.subscription_factory = subscription_factory
        self.inserter_factory = inserter_factory
        self.loop = loop
        
    async def handle_connection(self, reader, writer):
        try:
            resp = await network.read_json(reader)
            data_request = network.parse_data_request(resp)
            if(data_request.type == network.REQ_WRITE):
                await self.handle_input(reader, writer, data_request.config)
            elif(data_request.type == network.REQ_READ):
                await self.handle_output(reader, writer, data_request.config)
            else:
                await network.send_error(writer, "bad request type")
        except Exception as e:
            logging.warning("------- SERVER EXCEPTION LOG ----------------")
            for line in traceback.format_exception(
                    Exception, e, e.__traceback__):
                logging.warning(line.rstrip())
            logging.warning("------- END SERVER EXCEPTION LOG ------------")
            await network.send_error(writer, "Error: [%r]" % repr(e))

        writer.close()
        
    async def handle_input(self, reader, writer, dest_stream):
        (inserter, unsubscribe) = self.inserter_factory(dest_stream)
        if(inserter is None):
            raise Exception("cannot write to [%s]" % dest_stream.path)
        
        msg = "write to [%s] authorized" % dest_stream.path
        await network.send_ok(writer, msg)
        logging.info("server: write to [%s] started" % dest_stream.path)

        npipe = StreamNumpyPipeReader(dest_stream.layout, reader=reader)
        q = asyncio.Queue(loop=self.loop)
        coro = inserter.process(q, loop=self.loop)
        task = asyncio.ensure_future(coro)
        try:
            while(True):
                data = await npipe.read()
                npipe.consume(len(data))
                q.put_nowait(data)
                await asyncio.sleep(0.25)
        except (EmptyPipe, ConnectionResetError):
            logging.info("server: write to [%s] stopped" % dest_stream.path)
        finally:
            inserter.stop()
            await task
            unsubscribe()  # allow someone else to write to this stream
        
    async def handle_output(self, reader, writer, config):
        res = self.subscription_factory(config.path, config.time_range)
        (dest_stream, q, unsubscribe) = res
        msg = "%s" % dest_stream.layout
        await network.send_ok(writer, msg)
        npipe_w = StreamNumpyPipeWriter(dest_stream.layout, writer=writer)
        try:
            while(True):
                data = await q.get()
                await npipe_w.write(data)
                await asyncio.sleep(0.25)
        except ConnectionResetError:
            pass
        finally:
            unsubscribe()
        
        
def build_server(ip_addr, port,
                 subscription_factory,
                 inserter_factory,
                 loop=None):

    server = Server(subscription_factory, inserter_factory, loop=loop)
    coro = asyncio.start_server(server.handle_connection,
                                ip_addr, port, loop=loop)
    return coro

