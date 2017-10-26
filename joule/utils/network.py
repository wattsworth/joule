
import json
import collections
import logging
import configparser
from joule.daemon import stream 

STATUS_ERROR = 'error'
STATUS_OK = 'ok'

"""
DataRequest Definitions
-----------------------------------------
"""
DataRequest = collections.namedtuple("DataRequest", ["type", "config"])

"""
Request a stream to write into
config: stream object as JSON
"""
REQ_WRITE = 'write'

"""
Request a stream to read from
config:
    {
      path: /some/path,
      decimation: 1,
      time_range: [start, end]
    }
"""
REQ_READ = 'read'

ReaderConfig = collections.namedtuple("ReaderConfig",
                                      ["path", "decimation", "time_range"])


def parse_data_request(data_request):
    req_type = data_request['type']
    req_config = data_request['config']
    if(req_type == REQ_READ):
        return DataRequest(REQ_READ, ReaderConfig(req_config['path'],
                                                  req_config['decimation'],
                                                  req_config['time_range']))
    elif(req_type == REQ_WRITE):
        config = configparser.ConfigParser()
        config.read_dict(req_config)
        streamparser = stream.Parser()
        req_stream = streamparser.run(config)
        return DataRequest(REQ_WRITE, req_stream)
    else:
        raise Exception("invalid request type: %s" % type)

    
async def send_ok(writer, message=''):
    msg = {'status': STATUS_OK, 'message': message}
    await send_json(writer, msg)

    
async def send_error(writer, message):
    msg = {'status': STATUS_ERROR, 'message': message}
    await send_json(writer, msg)

    
async def send_json(writer, msg):
    msg = json.dumps(msg).encode('utf-8')
    data = bytes(msg)
    try:
        writer.write(len(data).to_bytes(4, byteorder='big'))
        writer.write(data)
        await writer.drain()
    except ConnectionResetError:
        addr = writer.get_extra_info('peername')
        logging.warning('failed to write to closed pipe [%s:%s]' % addr)

    
async def read_json(reader):
    # get the length of the json request
    b = await reader.read(4)
    size = int.from_bytes(b,
                          byteorder='big',
                          signed=False)
    # create a config object 
    raw = await reader.read(size)
    return json.loads(raw.decode())
