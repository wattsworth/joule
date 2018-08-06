import datetime


# parser for boolean args
def yesno(val):
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


def time_now():
    return datetime.datetime.now().timestamp() * 1e6


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
