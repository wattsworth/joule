"""
Asyncio Client for NilmDB
"""
import aiohttp
import numpy
import json

class AioNilmdb:

    def __init__(self,server):
        self.server = server 
        self.session = aiohttp.ClientSession()

    def close(self):
        self.session.close()
        
    async def stream_insert(self,path, data, start, end):

        url = "{server}/stream/insert".format(server=self.server)
        params = {"start":"%d"%start,
                  "end":"%d"%end,
                  "path":path,
                  "binary":'1'}
        # Convert to structured array
        width = numpy.shape(data)[1]-1
        my_dtype = numpy.dtype([('timestamp','<i8'),('data','<f8',width)])
        sarray = numpy.zeros(data.shape[0], dtype=my_dtype)
        try:
            sarray['timestamp'] = data[:,0]
            # Need the squeeze in case sarray['data'] is 1 dimensional
            sarray['data'] = numpy.squeeze(data[:,1:])
        except (IndexError, ValueError):
            raise ValueError("wrong number of fields for this data type")
        data = sarray

        async with self.session.put(url,params=params,
                                    data=data.tostring()) as resp:
            if(resp.status!=200):
                raise AioNilmdbError(await resp.text())

    async def stream_list(self,path,layout=None,extended=False):
      url = "{server}/stream/list".format(server=self.server)
      params = {"path":   path}
      async with self.session.get(url,params=params) as resp:
        body = await resp.text()
        if(resp.status!=200):
            raise AioNilmdbError(body)
        return json.loads(body)

    async def stream_create(self,path,layout):
      url = "{server}/stream/create".format(server=self.server)
      data = {"path":   path,
              "layout": layout}
      async with self.session.post(url,data=data) as resp:
        if(resp.status!=200):
            raise AioNilmdbError(await resp.text())
      return True



class AioNilmdbError(Exception):
    pass
