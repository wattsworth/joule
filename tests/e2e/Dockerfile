FROM ubuntu:latest

MAINTAINER John Donnal <donnal@usna.edu>


RUN apt-get update;
RUN apt-get install python2.7 python2.7-dev python-setuptools cython -y

# Base NilmDB dependencies
RUN apt-get install python-cherrypy3 python-decorator python-simplejson -y
RUN apt-get install python-requests python-dateutil python-tz -y
RUN apt-get install python-progressbar python-psutil -y

# Other dependencies (required by some modules)
#sudo apt-get install python-numpy -y
ADD nilmdb /nilmdb
WORKDIR /nilmdb

RUN python setup.py install
EXPOSE 80
CMD nilmdb-server -p 80

