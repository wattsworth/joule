FROM ubuntu:focal

MAINTAINER John Donnal <donnal@usna.edu>

ARG DEBIAN_FRONTEND=noninteractive
ENV TZ=America/New_York
RUN apt-get update && apt-get install python3 python3-pip language-pack-en postgresql -y

ADD requirements.txt /tmp
WORKDIR tmp
#RUN apt-get install libpq-dev libblas-dev liblapack-dev gfortran -y
#RUN pip3 install psycopg2-binary
RUN pip3 install --upgrade pip
RUN pip3 install --trusted-host pypi.python.org  -r requirements.txt

ENV LC_ALL en_US.UTF-8
ENV LANG en_US.UTF-8
ENV LANGUAGE en_US.UTF-8

ADD . /joule
WORKDIR /joule
RUN python3 setup.py -q install


CMD /usr/local/bin/jouled



