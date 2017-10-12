
import asyncio
import json
from . import server_utils


class Server:
    def __init__(self, path_workers, inserter_factory):
        self.path_workers = path_workers
        self.inserter_factory = inserter_factory
        
    async def handle_connection(self, reader, writer):
        try:
            r = await server_utils.read_json(reader)
            config = server_utils.create_config_from_json(r)

            if(config.direction == server_utils.DIR_WRITE):
                self.handle_input(reader, writer, config)
            elif(config.direction == server_utils.DIR_READ):
                self.handle_output(reader, writer, config)
            else:
                await server_utils.send_error(writer, "bad [direction] value")
        except KeyError as e:
            await server_utils.send_error(writer, "missing [%s] in config" % e)
        except:
            await server_utils.send_error(writer, "unknown error")
        writer.close()
        
    async def handle_input(self, reader, writer, config):
        await server_utils.send_ok(writer,
                                   "write to [%s] authorized" % config.path)

    async def handle_output(self, reader, writer, config):
        await server_utils.send_ok(writer)
        
        
def build_server(ip_addr, port,
                 path_workers,
                 inserter_factory,
                 loop=None):
    server = Server(path_workers, inserter_factory)
    coro = asyncio.start_server(server.handle_connection,
                                ip_addr, port, loop=loop)
    return coro

