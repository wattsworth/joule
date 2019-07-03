import aiohttp
import ssl
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
