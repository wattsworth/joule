from __future__ import absolute_import

import re
import time
import datetime_tz

# Range
min_timestamp = (-2**63)
max_timestamp = (2**63 - 1)

# Smallest representable step
epsilon = 1

def string_to_timestamp(str):
    """Convert a string that represents an integer number of microseconds
    since epoch."""
    try:
        # Parse a string like "1234567890123456" and return an integer
        return int(str)
    except ValueError:
        # Try parsing as a float, in case it's "1234567890123456.0"
        return int(round(float(str)))

def timestamp_to_string(timestamp):
    """Convert a timestamp (integer microseconds since epoch) to a string"""
    if isinstance(timestamp, float):
        return str(int(round(timestamp)))
    else:
        return str(timestamp)

def timestamp_to_human(timestamp):
    """Convert a timestamp (integer microseconds since epoch) to a
    human-readable string, using the local timezone for display
    (e.g. from the TZ env var)."""
    if timestamp == min_timestamp:
        return "(minimum)"
    if timestamp == max_timestamp:
        return "(maximum)"
    dt = datetime_tz.datetime_tz.fromtimestamp(timestamp_to_unix(timestamp))
    return dt.strftime("%a, %d %b %Y %H:%M:%S.%f %z")

def unix_to_timestamp(unix):
    """Convert a Unix timestamp (floating point seconds since epoch)
    into a NILM timestamp (integer microseconds since epoch)"""
    return int(round(unix * 1e6))
seconds_to_timestamp = unix_to_timestamp

def timestamp_to_unix(timestamp):
    """Convert a NILM timestamp (integer microseconds since epoch)
    into a Unix timestamp (floating point seconds since epoch)"""
    return timestamp / 1e6
timestamp_to_seconds = timestamp_to_unix

def rate_to_period(hz, cycles = 1):
    """Convert a rate (in Hz) to a period (in timestamp units).
    Returns an integer."""
    period = unix_to_timestamp(cycles) / float(hz)
    return int(round(period))

def parse_time(toparse):
    """
    Parse a free-form time string and return a nilmdb timestamp
    (integer microseconds since epoch).  If the string doesn't contain a
    timestamp, the current local timezone is assumed (e.g. from the TZ
    env var).
    """
    if toparse == "min":
        return min_timestamp
    if toparse == "max":
        return max_timestamp

    # If it starts with @, treat it as a NILM timestamp
    # (integer microseconds since epoch)
    try:
        if toparse[0] == '@':
            return int(toparse[1:])
    except (ValueError, KeyError, IndexError):
        pass

    # If string isn't "now" and doesn't contain at least 4 digits,
    # consider it invalid.  smartparse might otherwise accept
    # empty strings and strings with just separators.
    if toparse != "now" and len(re.findall(r"\d", toparse)) < 4:
        raise ValueError("not enough digits for a timestamp")

    # Try to just parse the time as given
    try:
        return unix_to_timestamp(datetime_tz.datetime_tz.
                                 smartparse(toparse).totimestamp())
    except (ValueError, OverflowError, TypeError):
        pass

    # If it's parseable as a float, treat it as a Unix or NILM
    # timestamp based on its range.
    try:
        val = float(toparse)
        # range is from about year 2001 - 2128
        if val > 1e9 and val < 5e9:
            return unix_to_timestamp(val)
        if val > 1e15 and val < 5e15:
            return val
    except ValueError:
        pass

    # Try to extract a substring in a condensed format that we expect
    # to see in a filename or header comment
    res = re.search(r"(^|[^\d])("            # non-numeric or SOL
                    r"(199\d|2\d\d\d)"       # year
                    r"[-/]?"                 # separator
                    r"(0[1-9]|1[012])"       # month
                    r"[-/]?"                 # separator
                    r"([012]\d|3[01])"       # day
                    r"[-T ]?"                # separator
                    r"([01]\d|2[0-3])"       # hour
                    r"[:]?"                  # separator
                    r"([0-5]\d)"             # minute
                    r"[:]?"                  # separator
                    r"([0-5]\d)?"            # second
                    r"([-+]\d\d\d\d)?"       # timezone
                    r")", toparse)
    if res is not None:
        try:
            return unix_to_timestamp(datetime_tz.datetime_tz.
                                     smartparse(res.group(2)).totimestamp())
        except ValueError:
            pass

    # Could also try to successively parse substrings, but let's
    # just give up for now.
    raise ValueError("unable to parse timestamp")

def now():
    """Return current timestamp"""
    return unix_to_timestamp(time.time())
