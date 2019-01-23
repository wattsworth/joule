import aiohttp
from joule.models import Stream
from enum import Enum
from typing import List

from joule.models.data_store import errors


class ERRORS(Enum):
    STREAM_ALREADY_EXISTS = "stream already exists at this path"
    NO_SUCH_STREAM = "No such stream"
    NO_STREAM_AT_PATH = "No stream at path"


def compute_path(stream: Stream, decimation_level: int = 1):
    path = "/joule/%d" % stream.id
    if decimation_level == 1:
        return path
    return path + "~decim-%d" % decimation_level


async def check_for_error(resp: aiohttp.ClientResponse, ignore: List[ERRORS] = None):
    if resp.status == 200:
        return  # OK
    try:
        error = await resp.json()
        if ignore is not None:
            for error_type in ignore:
                if error_type.value in error["message"]:
                    return  # OK
    except aiohttp.ContentTypeError:
        raise errors.DataError("[%d] invalid json response \"%s\"" % (resp.status, await resp.text()))
    raise errors.DataError("[%d]: %s" % (resp.status, error["message"]))
