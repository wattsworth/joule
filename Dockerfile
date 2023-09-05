FROM ubuntu:jammy

LABEL John Donnal <donnal@usna.edu>

ARG DEBIAN_FRONTEND=noninteractive
ENV TZ=America/New_York
ENV LC_ALL en_US.UTF-8
ENV LANG en_US.UTF-8
ENV LANGUAGE en_US.UTF-8

RUN apt-get update && \
    apt-get install -y locales python3.11 python3.11-dev python3-pip postgresql libpq-dev gettext libblas-dev liblapack-dev gfortran  libhdf5-dev git\
    && rm -rf /var/lib/apt/lists/* \
	&& localedef -i en_US -c -f UTF-8 -A /usr/share/locale/locale.alias en_US.UTF-8

# use python3.11
RUN update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.11 1
RUN update-alternatives --set python3 /usr/bin/python3.11

RUN mkdir /build
WORKDIR /build
ADD requirements.txt .
RUN pip3 install psycopg2-binary
RUN pip3 install --upgrade pip
RUN pip3 install --trusted-host pypi.python.org  -r requirements.txt

RUN apt-get update && apt-get install nginx gosu -y


COPY . /build/joule
RUN cd joule && pip install .

# setup the default configuration
ENV NODE_NAME joule
ENV POSTGRES_USER joule
ENV POSTGRES_PASSWORD joule
ENV POSTGRES_HOST postgres
ENV POSTGRES_PORT 5432
ENV POSTGRES_DB joule
ENV USER_KEY=ebf8d122e91478656b4b34755ecffc76ee60fe43f0569fd0b12573522fcb43c2
ENV HOST_PORT=80
ENV HOST_SCHEME=http

RUN mkdir /config
ADD docker/main.template.conf /config/main.template
ADD docker/user.template.conf /config/user.template
RUN mkdir /etc/joule && mkdir /stub
RUN cd / && rm -rf /build

# add nginx
ADD docker/nginx.conf /etc/nginx/nginx.conf
ADD docker/nginx-joule.conf /etc/nginx/templates/joule.conf.template
RUN rm /etc/nginx/sites-enabled/default

ADD docker/runner.sh .
ADD docker/nginx_scripts .
# allow the user to override the configuration by mounting a volume to /etc/joule
RUN mkdir -p /etc/joule/configs && \
    ln -s /config/main.conf /etc/joule/main.conf && \
    ln -s /config/user.conf /etc/joule/configs/user.conf

EXPOSE 80
# allow the user to override the user configuration by mounting a volume to /etc/joule/configs
CMD /bin/bash runner.sh



