from __future__ import absolute_import

import time
import datetime

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
    dt = datetime.datetime.fromtimestamp(timestamp_to_unix(timestamp))
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


def rate_to_period(hz, cycles=1):
    """Convert a rate (in Hz) to a period (in timestamp units).
    Returns an integer."""
    period = unix_to_timestamp(cycles) / float(hz)
    return int(round(period))


def now():
    """Return current timestamp"""
    return unix_to_timestamp(time.time())
