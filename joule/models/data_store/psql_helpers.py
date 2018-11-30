import numpy as np
import io
from struct import pack
import datetime
import asyncpg
from typing import List, Optional
import pdb
import asyncio
import re
import logging

from joule.errors import DataError
from joule.models.stream import Stream

log = logging.getLogger('joule')

postgres_ts_offset = 946684800000000  # January 1 2000 GMT


def data_to_bytes(data: np.ndarray) -> io.BytesIO:
    pgcopy_dtype = [("num_fields", ">i2"),
                    ("time_length", '>i4'),
                    ("time", '>i8')]
    dtype_tuple = data.dtype.descr[1]
    elem_dtype = dtype_tuple[1].replace('<', '>')
    elem_length = data['data'].dtype.alignment
    if len(dtype_tuple) == 3:
        n_elem = dtype_tuple[2][0]
    else:
        n_elem = 1
    for i in range(n_elem):
        pgcopy_dtype += [("elem%d_length" % i, '>i4'),
                         ("elem%d" % i, elem_dtype)]
    pgcopy = np.empty(data.shape, pgcopy_dtype)
    pgcopy['num_fields'] = n_elem+1
    pgcopy['time_length'] = 8
    pgcopy['time'] = data['timestamp']-postgres_ts_offset
    if n_elem == 1:
        pgcopy['elem0_length'] = elem_length
        pgcopy['elem0'] = data['data']
    else:
        for i in range(n_elem):
            pgcopy['elem%d_length' % i] = elem_length
            pgcopy['elem%d' % i] = data['data'][:, i]
    cpy = io.BytesIO()
    # signature, flag field and and header extension (both empty)
    cpy.write(pack('!11sii', b'PGCOPY\n\377\r\n\0', 0, 0))
    cpy.write(pgcopy.tostring())
    cpy.write(pack('!h', -1))
    cpy.seek(0)
    return cpy


def bytes_to_data(buffer: io.BytesIO, dtype:np.dtype) -> np.ndarray:
    pgcopy_dtype = [("num_fields", ">i2"),
                    ("time_length", '>i4'),
                    ("time", '>i8')]
    dtype_tuple = dtype.descr[1]
    elem_dtype = dtype_tuple[1].replace('<', '>')
    elem_length = dtype['data'].alignment
    if len(dtype_tuple)==3:
        n_elem = dtype_tuple[2][0]
    else:
        n_elem = 1
    for i in range(n_elem):
        pgcopy_dtype += [("elem%d_length" % i, '>i4'),
                         ("elem%d" % i, elem_dtype)]
    pgcopy_dtype = np.dtype(pgcopy_dtype)
    nbytes = buffer.seek(0, io.SEEK_END)
    buffer.seek(0)
    # check the header
    header = pack('!11sii', b'PGCOPY\n\377\r\n\0', 0, 0)
    rx_header = buffer.read(len(header))
    if rx_header != header:
        raise DataError("bad pgcopy header")
    row_size = pgcopy_dtype.itemsize
    if (nbytes - 21) % row_size != 0:
        raise DataError("invalid number of data bytes")
    nrows = (nbytes - 21) // row_size
    tuple_data = np.frombuffer(buffer.read(nbytes - 21), pgcopy_dtype)
    rx_data = np.empty(nrows, dtype)
    rx_data['timestamp'] = tuple_data['time'] + postgres_ts_offset
    if n_elem == 1:
        rx_data['data']=tuple_data['elem0']
    else:
        for i in range(n_elem):
            rx_data['data'][:, i] = tuple_data['elem%d' % i]
    # reader the footer
    footer = pack('!h', -1)
    rx_footer = buffer.read()
    if footer != rx_footer:
        raise DataError("ERROR: invalid footer")
    return rx_data


def query_time_bounds(start, end):
    # bounds are [ --- )
    limits = []
    if start is not None:
        if type(start) is not datetime.datetime:
            start = datetime.datetime.fromtimestamp(start / 1e6, tz=datetime.timezone.utc)
        limits.append("time >= '%s'" % start)
    if end is not None:
        if type(end) is not datetime.datetime:
            end = datetime.datetime.fromtimestamp(end / 1e6, tz=datetime.timezone.utc)
        limits.append("time < '%s'" % end)
    if len(limits) > 0:
        return 'WHERE ' + ' AND '.join(limits)
    else:
        return ''


async def create_stream_table(conn: asyncpg.Connection, stream: Stream):
    n_elems = len(stream.elements)
    # create the main table
    col_type = get_psql_type(stream.datatype)
    cols = ["elem%d %s NOT NULL"%(x, col_type) for x in range(n_elems)]
    sql = "CREATE TABLE IF NOT EXISTS joule.stream%d ("%stream.id +\
          "time TIMESTAMP NOT NULL," +\
          ', '.join(cols) + ");"
    await conn.execute(sql)
    sql = "SELECT create_hypertable('joule.stream%d', 'time', if_not_exists=>true);" % stream.id
    await conn.execute(sql)

    # create interval table
    sql = "CREATE TABLE IF NOT EXISTS joule.stream%d_intervals (" % stream.id + \
          "time TIMESTAMP NOT NULL);"
    await conn.execute(sql)


async def create_decimation_table(conn: asyncpg.Connection, stream: Stream, level: int):
    n_elems = len(stream.elements)
    table_name = 'joule.stream%d_%d' % (stream.id, level)
    # create decimation table (just a template)
    mean_cols = ["elem%d REAL NOT NULL" % x for x in range(n_elems)]
    min_cols = ["elem%d_min REAL NOT NULL" % x for x in range(n_elems)]
    max_cols = ["elem%d_max REAL NOT NULL" % x for x in range(n_elems)]
    cols = mean_cols + min_cols + max_cols
    sql = "CREATE TABLE IF NOT EXISTS %s (" % table_name + \
          "time TIMESTAMP NOT NULL," + \
          ', '.join(cols) + ");"
    await conn.execute(sql)
    sql = "SELECT create_hypertable('%s', 'time', if_not_exists=>true);" % table_name
    await conn.execute(sql)


def get_psql_type(x: Stream.DATATYPE):
    if x==Stream.DATATYPE.FLOAT32:
        return 'real'
    elif x==Stream.DATATYPE.FLOAT64:
        return 'double precision'
    elif x==Stream.DATATYPE.INT16:
        return 'smallint'
    elif x==Stream.DATATYPE.INT32:
        return 'integer'
    elif x==Stream.DATATYPE.INT64:
        return 'bigint'
    else:
        raise DataError("Invalid type [%r] for timescale backend" %x)


async def get_row_count(conn: asyncpg.Connection, stream: Stream,
                        start=None, end=None):
    if start is None and end is None:
        query = "SELECT row_estimate FROM hypertable_appproximate_row_count(joule.stream%d);"
        nrows = await conn.fetchval(query);
        if nrows<500:
            query = "SELECT count(*) from joule.stream%d " % stream.id
            return await conn.fetchval(query)
        return nrows
    # otherwise find the time bounds for the data
    if start is None:
        query = "SELECT time FROM joule.stream%d ORDER BY ASC LIMIT 1";
        start = await conn.fetchval(query)
    query = "EXPLAIN SELECT COUNT(*) FROM joule.stream%d " % stream.id
    query += query_time_bounds(start, end)
    records = await conn.fetch(query)
    if len(records)>1 and 'QUERY PLAN' in records[1]:
        plan = records[1]['QUERY PLAN']
        match = re.search("rows=(\d*)", plan)
        if match is not None:
            return int(match.group(1))
    logging.error("Cannot parse explain query:")
    for record in records:
        logging.error("\t %r" % record)

    # fallback to get the exact value
    query = "SELECT count(*) from joule.stream%d "% stream.id
    query += query_time_bounds(start, end)
    nrows = await conn.fetchval(query)
    return nrows


async def close_interval(conn: asyncpg.Connection, stream: Stream, ts: int):
    # place a boundary 1us *after* ts
    base_table = "joule.stream%d" % stream.id
    interval_table = "joule.stream%d_intervals" % stream.id
    ts = datetime.datetime.fromtimestamp(ts / 1e6, tz=datetime.timezone.utc)
    # find the most recent data before this boundary (ts)
    query = "SELECT time FROM %s WHERE time <= '%s' ORDER BY time DESC LIMIT 1" % (base_table, ts)
    last_ts = await conn.fetchval(query)
    if last_ts is None:
        # no data exists before ts so no need for an interval boundary
        return
    # check if this interval is necessary
    query = "SELECT time FROM %s WHERE time <= '%s' ORDER BY time DESC LIMIT 1" % (interval_table, ts)
    last_interval = await conn.fetchval(query)
    if last_interval is None or last_ts > last_interval:
        query = "INSERT INTO %s(time) VALUES ($1)" % interval_table
        await conn.execute(query, last_ts+datetime.timedelta(microseconds=1))


async def get_table_names(conn: asyncpg.Connection, stream: Stream) -> List[str]:

    query = '''select table_name from information_schema.tables 
               where table_schema='joule' 
               and table_type='BASE TABLE' 
               and table_name like 'stream%d%%';''' % stream.id
    records = await conn.fetch(query)
    return ['joule.'+r['table_name'] for r in records]


async def get_boundaries(conn: asyncpg.Connection, stream: Stream,
                        start: Optional[int], end: Optional[int]) -> List[datetime.datetime]:
    if start is None:
        query = "SELECT time FROM joule.stream%d ORDER BY time ASC LIMIT 1"% stream.id
        start = await conn.fetchval(query)
        if start is None:
            # remove intervals?
            return [] # no data so no need for intervals
    else:
        start = datetime.datetime.fromtimestamp(start / 1e6, tz=datetime.timezone.utc)
    if end is None:
        query = "SELECT time FROM joule.stream%d ORDER BY time DESC LIMIT 1"% stream.id
        end = await conn.fetchval(query) + datetime.timedelta(microseconds=1)
    else:
        end = datetime.datetime.fromtimestamp(start / 1e6, tz=datetime.timezone.utc)
    query = "SELECT time FROM joule.stream%d_intervals " % stream.id
    query += query_time_bounds(start, end)
    query += " ORDER BY time ASC"
    records = await conn.fetch(query)
    ts = [start] + [r['time'] for r in records] + [end]
    return [x.replace(tzinfo=datetime.timezone.utc) for x in ts]

