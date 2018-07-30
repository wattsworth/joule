from typing import Dict, Union
import requests
import click


def get(url: str, params=None) -> requests.Response:
    try:
        return requests.get(url, params=params)
    except requests.ConnectionError:
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
