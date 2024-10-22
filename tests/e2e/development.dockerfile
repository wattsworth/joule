##### DEVELOPMENT CONTAINER: INSTALLS JOULE FROM SOURCE #####
# RUN this docker file from the root of the joule project:
# $ joule> docker build -f docker/development.dockerfile -t wattsworth/joule:dev .
FROM debian:bookworm-slim
LABEL org.opencontainers.image.authors="John Donnal <donnal@usna.edu>"

ARG DEBIAN_FRONTEND=noninteractive

# setup the default configuration
ENV NODE_NAME=joule
ENV POSTGRES_USER=joule
ENV POSTGRES_PASSWORD=joule
ENV POSTGRES_HOST=postgres
ENV POSTGRES_PORT=5432
ENV POSTGRES_DB=joule
ENV USER_KEY=ebf8d122e91478656b4b34755ecffc76ee60fe43f0569fd0b12573522fcb43c2
ENV HOST_PORT=80
ENV HOST_SCHEME=http

RUN apt-get update && \
    apt-get install -y nginx libpq-dev python3-pip git gettext libhdf5-dev\
    python3-h5py pkg-config postgresql-client python3.11-venv\
    && pip install --upgrade pip  --break-system-packages\
    && rm -rf /var/lib/apt/lists/* \
    && rm /etc/nginx/sites-enabled/default

RUN mkdir /config && mkdir /stub && mkdir -p /etc/joule/configs && \
    ln -s /config/main.conf /etc/joule/main.conf && \
    ln -s /config/user.conf /etc/joule/configs/users.conf
COPY docker/main.template.conf /config/main.template
COPY docker/user.template.conf /config/user.template

COPY docker/nginx.conf /etc/nginx/nginx.conf
COPY docker/nginx-joule.conf /etc/nginx/templates/joule.conf.template
COPY docker/runner.sh .
RUN chmod +x runner.sh
COPY docker/nginx_scripts .

# install dependencies (should be cached)
RUN python3 -m venv venv
COPY ./requirements.txt .
RUN /venv/bin/pip3 install -r requirements.txt
RUN /venv/bin/pip3 install coverage
# joule is installed in the container since it is mounted as a volume
EXPOSE 80
# must override run command
CMD false


