import requests
import json
from .stream_info import StreamInfo


class Client:

    def __init__(self, server):
        self.server = server

    def dbinfo(self):
        """Return server database info (path, size, free space)
        as a dictionary."""
        return self._get("dbinfo")

    def stream_create(self, path, layout):
        url = "{server}/stream/create".format(server=self.server)
        data = {"path":   path,
                "layout": layout}
        r = requests.post(url, data=data)
        if(r.status_code != requests.codes.ok):
            raise NilmdbError(r.text)

    def stream_info(self, path):
        streams = self._get("stream/list",
                            params={"path": path})
        if (len(streams) == 0):
            return None
        else:
            return StreamInfo(self.server, streams[0])

    def stream_get_metadata(self, path, keys=None):
        """Get stream metadata"""
        params = {"path": path}
        if keys is not None:
            params["key"] = keys
        data = self._get("stream/get_metadata", params)
        return data

    def stream_set_metadata(self, path, data):
        """Set stream metadata from a dictionary, replacing all existing
        metadata."""
        params = {
            "path": path,
            "data": json.dumps(data)
        }
        return self._post("stream/set_metadata", params)

    def stream_update_metadata(self, path, data):
        """Update stream metadata from a dictionary"""
        params = {
            "path": path,
            "data": json.dumps(data)
            }
        return self._post("stream/update_metadata", params)

    def _get(self, path, params=None):
        url = "{server}/{path}".format(server=self.server,
                                       path=path)
        r = requests.get(url, params=params)
        if(r.status_code != requests.codes.ok):
            raise NilmdbError(r.text)
        return json.loads(r.text)

    def _post(self, path, data):
        url = "{server}/{path}".format(server=self.server,
                                       path=path)
        r = requests.post(url, data=data)
        if(r.status_code != requests.codes.ok):
            raise NilmdbError(r.text)

        
class NilmdbError(Exception):
    pass
