from datetime import datetime, timezone


# --------- Utility functions from Jim Paris ------------


def time_now() -> int:
    """
    :return:     current time in UNIX microseconds
    """
    return int(datetime.now().timestamp() * 1e6)


# Range
min_timestamp = (-2 ** 63)
max_timestamp = (2 ** 63 - 1)


def timestamp_to_human(timestamp: int) -> str:
    """Convert a timestamp (integer microseconds since epoch) to a
    human-readable string, using the local timezone for display
    (e.g. from the TZ env var)."""
    if timestamp == min_timestamp:
        return "(minimum)"
    if timestamp == max_timestamp:
        return "(maximum)"
    dt = datetime.fromtimestamp(timestamp_to_unix(timestamp))
    return dt.strftime("%a, %d %b %Y %H:%M:%S %z")


def human_to_timestamp(time: str) -> int:
    """Convert a time specification into a UNIX microsecond timestamp. Time specification
        may be a wide variety of date formats, relative interval such as "one minute ago", or a numeric
        timestamp. Raises :exc:ValueError for invalid time specification"""
    import dateparser

    try:
        return int(time)
    except ValueError:
        pass
    time = dateparser.parse(time)
    if time is None:
        raise ValueError
    return int(time.timestamp() * 1e6)


def unix_to_timestamp(unix):
    """Convert a Unix timestamp (floating point seconds since epoch)
    into a NILM timestamp (integer microseconds since epoch)"""
    return int(round(unix * 1e6))


def timestamp_to_datetime(timestamp: int):
    return datetime.fromtimestamp(timestamp / 1e6, timezone.utc) 


def datetime_to_timestamp(date: datetime):
    # if it is a naive datetime, assume it is UTC, and convert it to a timestamp
    if date.tzinfo is None:
        return int(date.replace(tzinfo=timezone.utc).timestamp() * 1e6)
    # if it is an aware datetime, convert it to a timestamp
    return int(date.timestamp() * 1e6)


seconds_to_timestamp = unix_to_timestamp


def timestamp_to_unix(timestamp):
    """Convert a NILM timestamp (integer microseconds since epoch)
    into a Unix timestamp (floating point seconds since epoch)"""
    return timestamp / 1e6


timestamp_to_seconds = timestamp_to_unix
