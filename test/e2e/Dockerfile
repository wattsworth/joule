FROM jdonnal/joule:patched_nilmdb

MAINTAINER John Donnal <donnal@usna.edu>

#RUN apt-get update; apt-get install python3-dev python3-setuptools python3-scipy -y
#RUN rm /bin/sh && ln -s /bin/bash /bin/sh
RUN apt-get install python3-pip -y
RUN pip3 uninstall Joule -y
RUN python3 setup.py install
ADD . /src
WORKDIR /src
CMD /bin/bash
