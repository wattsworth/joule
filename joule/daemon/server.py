
import traceback
import asyncio
import logging
from joule.utils.numpypipe import StreamNumpyPipeReader, StreamNumpyPipeWriter
from joule.utils import network


class Server:
    def __init__(self, reader_factory, inserter_factory, loop=None):
        self.reader_factory = reader_factory
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
                logging.warning(line)
            logging.warning("------- END SERVER EXCEPTION LOG ------------")
            await network.send_error(writer, "Error: [%r]" % e)

        writer.close()
        
    async def handle_input(self, reader, writer, dest_stream):
        inserter = self.inserter_factory(dest_stream)
        if(inserter is None):
            msg = "cannot write to requested path"
            await network.send_error(writer, msg)
            return
        
        msg = "write to [%s] authorized" % dest_stream.path
        await network.send_ok(writer, msg)

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
        except ConnectionResetError:
            pass
        except Exception as e:
            logging.warning("networked stream writer failed: %r" % e)
            raise e
        inserter.stop()
        await task            
        
    async def handle_output(self, reader, writer, config):
        npipe_r = self.reader_factory(config.path, config.time_range)
        if(npipe_r is None):
            msg = "path [%s] is unavailable"
            await network.send_error(writer, msg)
            return
        msg = "%s" % npipe_r.layout
        await network.send_ok(writer, msg)
        npipe_w = StreamNumpyPipeWriter(npipe_r.layout, writer=writer)
        try:
            while(True):
                data = await npipe_r.read()
                await npipe_w.write(data)
                npipe_r.consume(len(data))
                await asyncio.sleep(0.25)
        except ConnectionResetError:
            pass
        except Exception as e:
            logging.warning("networked stream reader failed: %r" % e)
        
        
def build_server(ip_addr, port,
                 reader_factory,
                 inserter_factory,
                 loop=None):
    server = Server(reader_factory, inserter_factory, loop=loop)
    coro = asyncio.start_server(server.handle_connection,
                                ip_addr, port, loop=loop)
    return coro

