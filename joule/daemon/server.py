
import asyncio
import logging
from joule.utils.numpypipe import (
    StreamNumpyPipeReader,
    StreamNumpyPipeWriter,
    EmptyPipe)
from joule.utils import network
import traceback

class Server:
    def __init__(self, subscription_factory, inserter_factory, loop=None):
        self.subscription_factory = subscription_factory
        self.inserter_factory = inserter_factory
        self.loop = loop
        self.stop_requested = False

    def stop_readers(self):
        self.stop_requested = True
        
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
            logging.warning("SERVER EXCEPTION: %s" % str(e))

            logging.warning("------- SERVER EXCEPTION LOG ----------------")
            for line in traceback.format_exception(
                    Exception, e, e.__traceback__):
                logging.warning(line.rstrip())
            logging.warning("------- END SERVER EXCEPTION LOG ------------")

            await network.send_error(writer, str(e)) #"Error: [%r]" % repr(e))
        writer.close()
        
    async def handle_input(self, reader, writer, config):
        (inserter, unsubscribe) = await self.inserter_factory(config.stream,
                                                              config.time_range)
        msg = "write to [%s] authorized" % config.stream.path
        await network.send_ok(writer, msg)
        logging.info("server: write to [%s] started" % config.stream.path)

        npipe = StreamNumpyPipeReader(config.stream.layout, reader=reader)
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
            pass
        finally:
            inserter.stop()
            await task
            logging.info("server: write to [%s] stopped" % config.stream.path)
            unsubscribe()  # allow someone else to write to this stream
        
    async def handle_output(self, reader, writer, config):
        res = self.subscription_factory(config.path, config.time_range)
        (layout, q, unsubscribe) = res
        logging.info("server: read from [%s] started" % config.path)
        await network.send_ok(writer, layout)
        npipe_w = StreamNumpyPipeWriter(layout, writer=writer)
        try:
            while(True):
                data = await q.get()
                if(data is None):
                    break
                await npipe_w.write(data)
                print("!!!sent data!!!")
                await asyncio.sleep(0.25)
        except ConnectionResetError:
            pass
        finally:
            logging.info("server: read from [%s] stopped" % config.path)
            unsubscribe()
        
        
def build_server(ip_addr, port,
                 subscription_factory,
                 inserter_factory,
                 loop=None):

    server = Server(subscription_factory, inserter_factory, loop=loop)
    coro = asyncio.start_server(server.handle_connection,
                                ip_addr, port, loop=loop)
    return coro

