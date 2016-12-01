"""
Asyncio Client for NilmDB
"""
import aiohttp
import numpy

class AioNilmdb:

    def __init__(self,server):
        self.session = None 
        self.server = server
        
    async def stream_insert(self,path, data, start, end):
#        session = await self._get_session()
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

        async with aiohttp.ClientSession() as session:
            async with session.put(url,params=params,
                                   data=data.tostring()) as resp:
                if(resp.status!=200):
                    print(await resp.text())

    async def _get_session(self):
        if(self.session is not None):
            return self.session
        else:
            self.session = await aiohttp.ClientSession()
            return self.session

    def stream_list(self,path):
        pass

    def get_stream_info(self,path):
        pass

    def stream_create(self,path,format):
        pass
