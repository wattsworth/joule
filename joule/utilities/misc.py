import aiohttp
import ssl
import numpy as np
from aiohttp.client_exceptions import ClientError
from typing import Optional


# parser for boolean args
def yesno(val: str):
    """
    Convert a "yes" or "no" argument into a boolean value. Returns ``true``
    if val is "yes" and ``false`` if val is "no". Raises ValueError otherwise.
    This is function can be used as the **type** parameter for to handle module arguments
    that are "yes|no" flags.
    """
    if val is None:
        raise ValueError("must be 'yes' or 'no'")
    # standardize the string
    val = val.lower().strip()
    if val == "yes":
        return True
    elif val == "no":
        return False
    else:
        raise ValueError("must be 'yes' or 'no'")


async def detect_url(host, port: Optional[int] = None):  # pragma: no cover
    if port is not None:
        host = host + ":" + str(port)

    ssl_context = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE

    async with aiohttp.ClientSession(conn_timeout=5) as session:
        # try to connect over https
        try:
            async with session.get("https://" + host, ssl_context=ssl_context) as resp:
                pass
            return "https://" + host
        except ClientError as e:
            # try again over http
            try:
                async with session.get("http://" + host) as resp:
                    pass
                return "http://" + host
            except ClientError:
                return None

def timestamps_are_monotonic(data, last_ts: Optional[int], name: str):
    if len(data) == 0:
        return True
    # if there are multiple rows, check that all timestamps are increasing
    if len(data) > 1 and np.min(np.diff(data['timestamp'])) <= 0:
        min_idx = np.argmin(np.diff(data['timestamp']))
        msg = ("Non-monotonic timestamp in new data to stream [%s] (%d<=%d)" %
               (name, data['timestamp'][min_idx + 1], data['timestamp'][min_idx]))
        print(msg)
        return False
    # check to make sure the first timestamp is larger than the previous block
    if last_ts is not None:
        if last_ts >= data['timestamp'][0]:
            msg = ("Non-monotonic timestamp between writes to stream [%s] (%d<=%d)" %
                   (name, data['timestamp'][0], last_ts))
            print(msg)
            return False
    return True

def validate_values(data):
    if np.isnan(data['timestamp']).any():
        return False
    if np.isnan(data['data']).any():
        return False
    return True
