import json
import aiohttp
import logging
import asyncio
import re
import traceback

from .. import numpypipe

class AsyncClient:

    def __init__(self, server):
        self.server = server
        self.session = aiohttp.ClientSession()

    def close(self):
        self.session.close()

    async def stream_insert(self, path, data, start, end, retry=True):
        """insert stream data, retry on error"""
        url = "{server}/stream/insert".format(server=self.server)
        params = {"start": "%d" % start,
                  "end": "%d" % end,
                  "path": path,
                  "binary": '1'}
        success = False
        while(success is False):
            try:
                async with self.session.put(url, params=params,
                                            data=data.tostring()) as resp:
                    if(resp.status != 200):
                        error = await resp.text()
                        if(resp.status == 400):
                            # nilmdb rejected the data because
                            # something is wrong with it
                            logging.error("nilmdb error, " +
                                          "dumped bad data [%s]" % error)
                            success = True
                        else:
                            # nilmdb itself has an error, we can retry
                            raise AioNilmdbError(error)
                    else:
                        success = True
            except Exception as e:
                self.session.close()
                self.session = aiohttp.ClientSession()
                if(retry is False):
                    raise AioNilmdbError from e
                else:
                    logging.error("nilmdb error: [%s], retrying" % e)
                    await asyncio.sleep(0.1)

    async def stream_extract(self, dest_queue, path, layout, start, end):
        url = "{server}/stream/extract".format(server=self.server)
        params = {"path":   path,
                  "start":  start,
                  "end":    end,
                  "binary": 1}
        try:
            async with self.session.get(url, params=params) as resp:
                reader = numpypipe.StreamNumpyPipeReader(layout, resp.content)
                while(True):
                    try:
                        data = await reader.read()
                        await dest_queue.put(data)
                        reader.consume(len(data))
                    except numpypipe.EmptyPipe:
                        break
        except Exception as e:
            for line in traceback.format_exception(
                    Exception, e, e.__traceback__):
                print(line)
        await dest_queue.put(None)
        
    async def stream_auto_remove(self, path, start, end, retry=True):
       """ remove [start,end] in path and all decimations """
       all_streams = await self.stream_list()
       all_paths = [x[0] for x in all_streams]
       regex=re.compile("%s~decim-(\d)+$"%path)       
       decim_paths = list(filter(regex.match, all_paths))
       return await self.streams_remove([path]+decim_paths, start, end, retry)
   
    async def streams_remove(self, paths, start, end, retry=True):
        """ remove data from an array of paths (eg base+decimations)"""
        for path in paths:
            await self.stream_remove(path, start, end, retry)
            
    async def stream_remove(self, path, start, end, retry=True):
        """remove data from streams, retry on error"""
        url = "{server}/stream/remove".format(server=self.server)
        params = {"start": "%d" % start,
                  "end": "%d" % end,
                  "path": path}
        success = False
        while(success is False):
            try:
                async with self.session.post(url, params=params) as resp:
                    if(resp.status != 200):
                        error = await resp.text()
                        logging.error("nilmdb error removing data: %s"
                                      % error)
                        # session was probably closed, retry
                        raise AioNilmdbError(error)
                    else:
                        success = True
            except Exception as e:
                self.session.close()
                self.session = aiohttp.ClientSession()
                if(retry is False):
                    raise AioNilmdbError from e
                else:
                    logging.error("nilmdb error: [%s], retrying" % e)
                    await asyncio.sleep(0.1)
                    
    async def stream_list(self, path=None, layout=None, extended=False):
        """ set path to None to list all streams """
        url = "{server}/stream/list".format(server=self.server)
        if(path is not None):
            params = {"path":   path}
        else:
            params = {}
            
        async with self.session.get(url, params=params) as resp:
            body = await resp.text()
            if(resp.status != 200):
                raise AioNilmdbError(body)
            return json.loads(body)

    async def stream_create(self, path, layout):
        url = "{server}/stream/create".format(server=self.server)
        data = {"path":   path,
                "layout": layout}
        async with self.session.post(url, data=data) as resp:
            if(resp.status != 200):
                raise AioNilmdbError(await resp.text())
        return True

    
class AioNilmdbError(Exception):
    pass
