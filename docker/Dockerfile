##### PRODUCTION CONTAINER: INSTALLS JOULE FROM PYPI #####
# RUN this docker file from the docker directory, provide a version number:
# $ joule/docker> docker build -f development.dockerfile -t wattsworth/joule:X.Y.Z .

FROM debian:bookworm-slim
LABEL John Donnal <donnal@usna.edu>

ARG DEBIAN_FRONTEND=noninteractive

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

RUN apt-get update && \
    apt-get install -y nginx libpq-dev python3-pip git gettext libhdf5-dev python3-h5py pkg-config\
    && pip install --upgrade pip  --break-system-packages\
    && pip install joule==0.11.0rc1  --break-system-packages\
    && rm -rf /var/lib/apt/lists/* \
    && rm /etc/nginx/sites-enabled/default


RUN mkdir /config && mkdir /stub && mkdir -p /etc/joule/configs && \
    ln -s /config/main.conf /etc/joule/main.conf && \
    ln -s /config/user.conf /etc/joule/configs/users.conf
COPY main.template.conf /config/main.template
COPY user.template.conf /config/user.template

COPY nginx.conf /etc/nginx/nginx.conf
COPY nginx-joule.conf /etc/nginx/templates/joule.conf.template

COPY runner.sh .
RUN chmod +x runner.sh
COPY nginx_scripts .
# allow the user to override the configuration by mounting a volume to /etc/joule


EXPOSE 80
# allow the user to override the user configuration by mounting a volume to /etc/joule/configs
CMD ./runner.sh



