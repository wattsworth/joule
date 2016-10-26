FROM jdonnal/nilmdb:installed

MAINTAINER John Donnal <donnal@usna.edu>

RUN apt-get update; apt-get install python3-dev python3-setuptools python3-scipy -y
RUN rm /bin/sh && ln -s /bin/bash /bin/sh
ADD nilmdb /nilmdb
ADD nilmtools /nilmtools
WORKDIR /nilmdb
RUN python3 setup.py install
WORKDIR /nilmtools
RUN python3 setup.py install
VOLUME /etc/joule
VOLUME /joule

CMD /bin/bash
