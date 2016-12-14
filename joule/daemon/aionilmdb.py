"""
Asyncio Client for NilmDB
"""
import aiohttp
import numpy
import json
import joule.utils.time

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

    def stream_create_nowait(self,path,layout):
      url = "{server}/stream/create".format(server=self.server)
      data = {"path":   path,
              "layout": layout}
      r = requests.post(url,data=data)
      if(r.status_code != requests.codes.ok):
          raise AioNilmdbError(r.text)

    def stream_info_nowait(self,path):
      url = "{server}/stream/list".format(server=self.server)
      params = {"path":   path}
      r = requests.get(url,params = params)
      if(r.status_code != requests.codes.ok):
          raise AioNilmdbError(r.text)
      stream = json.loads(body)[0]
      return StreamInfo(stream)


class StreamInfo(object):
    def __init__(self, url, info):
        self.url = url
        self.info = info
        try:
            self.path = info[0]
            self.layout = info[1]
            self.layout_type = self.layout.split('_')[0]
            self.layout_count = int(self.layout.split('_')[1])
            self.total_count = self.layout_count + 1
            self.timestamp_min = info[2]
            self.timestamp_max = info[3]
            self.rows = info[4]
            self.seconds = joule.utils.time.timestamp_to_seconds(info[5])
        except IndexError as TypeError:
            pass
    def string(self, interhost):
        """Return stream info as a string.  If interhost is true,
        include the host URL."""
        if interhost:
            return sprintf("[%s] ", self.url) + str(self)
        return str(self)

    def __str__(self):
        """Return stream info as a string."""
        return sprintf("%s (%s), %.2fM rows, %.2f hours",
                       self.path, self.layout, self.rows / 1e6,
                       self.seconds / 3600.0)

class AioNilmdbError(Exception):
    pass
