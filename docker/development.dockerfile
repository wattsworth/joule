# RUN this docker file from the root of the joule project:
# $ joule> docker build -f docker/development.dockerfile -t wattsworth/joule:dev .
FROM debian:bookworm-slim
LABEL John Donnal <donnal@usna.edu>

ARG DEBIAN_FRONTEND=noninteractive
#ENV TZ=America/New_York
#ENV LC_ALL en_US.UTF-8
#ENV LANG en_US.UTF-8
#ENV LANGUAGE en_US.UTF-8


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

#RUN apt-get update && \
#    apt-get install -y nginx locales python3.11 python3.11-dev python3-pip postgresql libpq-dev gettext libblas-dev liblapack-dev gfortran  libhdf5-dev git\
#    && rm -rf /var/lib/apt/lists/* \
#	&& localedef -i en_US -c -f UTF-8 -A /usr/share/locale/locale.alias en_US.UTF-8

RUN apt-get update && \
    apt-get install -y nginx libpq-dev python3-pip git gettext postgresql-client\
    && rm -rf /var/lib/apt/lists/* \
    && rm /etc/nginx/sites-enabled/default
    #&& localedef -i en_US -c -f UTF-8 -A /usr/share/locale/locale.alias en_US.UTF-8



RUN mkdir /config && mkdir /stub && mkdir -p /etc/joule/configs && \
    ln -s /config/main.conf /etc/joule/main.conf && \
    ln -s /config/user.conf /etc/joule/configs/users.conf
COPY docker/main.template.conf /config/main.template
COPY docker/user.template.conf /config/user.template

COPY docker/nginx.conf /etc/nginx/nginx.conf
COPY docker/nginx-joule.conf /etc/nginx/templates/joule.conf.template

# add a local copy of joule
#COPY src/joule /joule
#WORKDIR /joule
COPY . /joule
WORKDIR /joule
RUN pip3 install .  --break-system-packages

COPY docker/runner.sh .
COPY docker/nginx_scripts .
# allow the user to override the configuration by mounting a volume to /etc/joule


EXPOSE 80
# allow the user to override the user configuration by mounting a volume to /etc/joule/configs
CMD /bin/bash runner.sh



