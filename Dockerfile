FROM ubuntu:latest

MAINTAINER John Donnal <donnal@usna.edu>

RUN apt-get update;
RUN apt-get install python3 python3-dev python-setuptools python3-pip -y
RUN pip3 install --upgrade pip
RUN pip3 install cliff numpy psutil python-datetime-tz requests aiohttp

ADD . /joule
WORKDIR joule
RUN python3 setup.py -q install

CMD /bin/bash



