from typing import Dict, Union
import requests
import click


def get(url: str, params=None) -> requests.Response:
    try:
        return requests.get(url, params=params)
    # this method is used by data copy to check if the destination
    # stream is available, any connection errors should be caught by
    # the check for the source stream which occurs first
    except requests.ConnectionError:  # pragma: no cover
        click.echo("Error contacting Joule server at [%s]" % url)
        exit(1)


def get_json(url: str, params=None) -> Dict:

    resp = None  # to appease type checker
    try:
        resp = requests.get(url, params=params)
    except requests.ConnectionError:
        click.echo("Error contacting Joule server at [%s]" % url)
        exit(1)
    if resp.status_code != 200:
        click.echo("Error %s [%d]: %s" % (url, resp.status_code, resp.text))
        exit(1)
    try:
        data = resp.json()
        return data
    except ValueError:
        click.echo("Error: Invalid server response, check the URL")
        exit(1)


def post_json(url: str, data) -> Dict:
    resp = None  # to appease type checker
    try:
        resp = requests.put(url, data=data)
    except requests.ConnectionError:
        print("Error contacting Joule server at [%s]" % url)
        exit(1)
    if resp.status_code != 200:
        print("Error [%d]: %s" % (resp.status_code, resp.text))
        exit(1)
    try:
        return resp.json()
    except ValueError:
        click.echo("Error: Invalid server response, check the URL")
        exit(1)
