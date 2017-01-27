FROM ubuntu:latest

MAINTAINER John Donnal <donnal@usna.edu>

RUN apt-get update
RUN apt-get install python3 python3-pip python3-numpy python3-scipy python3-yaml -y
RUN pip3 install python-datetime-tz cliff psutil requests aiohttp

ADD . /joule
WORKDIR joule
RUN python3 setup.py -q install

RUN mkdir -p /etc/joule/stream_configs
RUN mkdir -p /etc/joule/module_configs
RUN touch /etc/joule/main.conf

CMD /usr/local/bin/jouled



