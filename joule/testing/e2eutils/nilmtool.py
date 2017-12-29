
import requests
import numpy as np
import json
from io import StringIO

NILMDB_URL = "http://nilmdb"

def create_stream(path, layout, url=NILMDB_URL ):
    url = "{url}/stream/create".format(url=url)
    data = {"path":   path,
            "layout": layout}
    req = requests.post(url, data=data)
    if(req.status_code != 200):
        raise Exception('cannot create stream [%s] on nilmdb server' % path)

    
def data_count(path, interval=None, url=NILMDB_URL):
    if(interval is None):
        req = requests.get(
            "{url}/stream/extract?path={path}&count=1".format(url=url, path=path))
    else:
        req = requests.get("{url}/stream/extract?path={path}&start={start}&end={end}&count=1".format(
            url=url, path=path, start=interval[0], end=interval[1]))

    return int(req.text)


def layout(path, url=NILMDB_URL):
    req = requests.get(
        "{url}/stream/list?path={path}".format(url=url, path=path))
    pathinfo = json.loads(req.text)
    return pathinfo[0][1]  # layout from first entry


def data_extract(path, interval=None, url=NILMDB_URL):
    if(interval is None):
        req = requests.get(
            "{url}/stream/extract?path={path}".format(url=url, path=path))
    else:
        req = requests.get("{url}/stream/extract?path={path}&start={start}&end={end}".format(
            url=url, path=path, start=interval[0], end=interval[1]))

    return np.loadtxt(StringIO(req.text))


def intervals(path, url=NILMDB_URL):
    all_intervals = list(gen_intervals(path, url=url))
    return all_intervals


def gen_intervals(path, url=NILMDB_URL):
    response = requests.get(
        "{url}/stream/intervals?path={path}".format(url=url, path=path),
        stream=True)

    def lines(source, ending):
        pending = None
        for chunk in source:
            if pending is not None:
                chunk = pending + chunk
            tmp = chunk.split(ending)
            lines = tmp[:-1]
            if chunk.endswith(ending):
                pending = None
            else:
                pending = tmp[-1]
            for line in lines:
                yield line
        if pending is not None:  # pragma: no cover (missing newline)
            yield pending



    for line in lines(response.iter_content(chunk_size = 1),
                      ending = b'\r\n'):
        yield json.loads(line.decode('ascii'))


def is_decimated(path, level=16, min_size=10, url=NILMDB_URL):
    dec_path = path + "~decim-%d" % level
    req = requests.get(
        "{url}/stream/extract?path={path}&count=1".format(url=url, path=dec_path))
    return int(req.text) > min_size



