import aiohttp
import re
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


async def detect_url(host, port: Optional[int] = None):  
    if port is not None:
        host = host + ":" + str(port)

    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(5)) as session:
        # try to connect over https
        try:
            await session.get("https://" + host)
            return "https://" + host
        except ClientError:
            # try again over http
            try:
                await session.get("http://" + host)
                return "http://" + host
            # unable to determine the URL
            except ClientError:
                return None

def parse_time_interval(time_interval: str) -> int:
    if time_interval.lower() == "all":
        return -1
    elif time_interval.lower() == "none":
        return 0
    match = re.fullmatch(r'^(\d+)([shdwmy])$', time_interval)
    if match is None:
        raise ValueError(f"use format #unit (eg 1w), none or all, {time_interval} not recognized")

    units = {
        's': 60 * 1e6, # seconds
        'h': 60 * 60 * 1e6,  # hours
        'd': 24 * 60 * 60 * 1e6,  # days
        'w': 7 * 24 * 60 * 60 * 1e6,  # weeks
        'm': 4 * 7 * 24 * 60 * 60 * 1e6,  # months
        'y': 365 * 24 * 60 * 60 * 1e6  # years
    }
    unit = match.group(2)
    time = int(match.group(1))
    if time <= 0:
        raise ValueError("use format #unit (eg 1w), none or all")
    return int(time * units[unit])