FROM ubuntu:latest

MAINTAINER John Donnal <donnal@usna.edu>


RUN apt-get update
RUN apt-get install python3 python3-pip language-pack-en -y

ADD requirements.txt /tmp
WORKDIR tmp
RUN pip3 install --trusted-host pypi.python.org  -r requirements.txt

ENV LC_ALL en_US.UTF-8
ENV LANG en_US.UTF-8
ENV LANGUAGE en_US.UTF-8

ADD . /joule
WORKDIR /joule
RUN python3 setup.py -q install


CMD /usr/local/bin/jouled



