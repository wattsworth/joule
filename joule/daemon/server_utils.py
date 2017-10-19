
import json
import collections
import logging
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


def parse_request_config(j):
    try:
        type = j['type']
        config = j['config']
        if(type == REQ_READ):
            return ReaderConfig(config['path'],
                                config['decimation'],
                                config['time_range'])
        elif(type == REQ_WRITE):
            return stream.from_json(config)  # TODO
        else:
            raise Exception("invalid type: %s" % type)
    except Exception as e:
        logging.warning("cannot parse json config: %r" % e)
        return None
        

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
    try:
        b = await reader.read(4)
        size = int.from_bytes(b,
                              byteorder='big',
                              signed=False)
        # create a config object 
        raw = await reader.read(size)
        return json.loads(raw.decode())
    except json.decoder.JSONDecodeError:
        logging.warning('invalid json')
        return None
