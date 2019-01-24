from typing import Dict
import requests

from joule.errors import ConnectionError

# NOTE: These are only used by the copy command!

def get(url: str, params=None) -> requests.Response:
    try:
        return requests.get(url, params=params)
    # this method is used by data copy to check if the destination
    # stream is available, any connection errors should be caught by
    # the check for the source stream which occurs first
    except requests.ConnectionError:  # pragma: no cover
        msg = "Cannot contact Joule server at [%s]" % url
        raise ConnectionError(msg)


def get_json(url: str, params=None) -> Dict:
    try:
        resp = requests.get(url, params=params)
    except requests.ConnectionError as e:
        raise ConnectionError("Cannot contact Joule server at [%s]" % url) from e
    if resp.status_code != 200:
        raise ConnectionError("%s [%d]: %s" % (url,
                                                     resp.status_code,
                                                     resp.text))
    try:
        data = resp.json()
        return data
    except ValueError as e:
        raise ConnectionError("Invalid server response, check the URL") from e
