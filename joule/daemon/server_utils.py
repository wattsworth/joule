
import json
import collections
import logging

"""
{
  path: /some/path,
  direction: write,
  layout: float32_3 
  configuration: { }
}
{
  path: /some/path,
  direction: read,
  decimation: 1,
  time_range: [start, end]
}
"""

DIR_READ = 'read'
DIR_WRITE = 'write'

STATUS_ERROR = 'error'
STATUS_OK = 'ok'

WriterConfig = collections.namedtuple("Config", ["path",
                                                 "direction",
                                                 "layout",
                                                 "configuration"])

ReaderConfig = collections.namedtuple("ReaderConfig", ["path",
                                                       "direction",
                                                       "decimation",
                                                       "time_range"])


def create_reader_config(path, decimation=1, time_range=None):
    return ReaderConfig(path, DIR_READ, decimation, time_range)


def create_config_from_json(j):
    try:
        if(j['direction'] == DIR_READ):
            return ReaderConfig(j['path'], DIR_READ,
                                j['decimation'], j['time_range'])
        elif(j['direction'] == DIR_WRITE):
            return WriterConfig(j['path'], DIR_WRITE,
                                j['layout'], j['configuration'])
        else:
            raise KeyError
    except Exception as e:
        logging.warning("cannot parse json config: %r" % e)
        return None
        

def create_writer_config(path, stream_configuration):
    return WriterConfig(path, DIR_WRITE, stream_configuration)


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
