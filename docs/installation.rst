.. _installation:

=====================
Installing Wattsworth
=====================

Here are the steps to install the Wattsworth software stack:

1. Rasbian
2. Python
3. Python Packages

Raspberry Pi
** tested on 64 bit Raspberry Pi OS on Raspberry Pi 4 **

# update and upgrade
sudo apt-get update
sudo apt-get upgrade -y

# install Docker
curl -sSL https://get.docker.com | sh
-or-
1. Remove old versions of Docker
for pkg in docker.io docker-doc docker-compose podman-docker containerd runc; do sudo apt-get remove $pkg; done
2. Install Docker
sudo apt-get install ca-certificates curl gnupg
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/raspbian/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg
echo \
  "deb [arch="$(dpkg --print-architecture)" signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/debian \
  "$(. /etc/os-release && echo "$VERSION_CODENAME")" stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt-get update
sudo apt-get install docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin -y

3. Confirm Docker works
sudo docker run hello-world

Install TimescaleDB + Postgres
==============================
sudo mkdir /opt/timescaledb

..Docker compose file => /opt/timescaledb/docker-compose.yml
version: "3.9"

services:
  postgres:
    image: timescale/timescaledb:latest-pg15
    restart: always
    environment:
      POSTGRES_USER: joule
      POSTGRES_PASSWORD: joule
      POSTGRES_DB: joule
    volumes:
      - /opt/timescaledb/data:/var/lib/postgresql/data  # persist data
    ports:
      - 5432:5432

..Service file
[Unit]
Description=TimescaleDB
After=docker.service

[Service]
Type=simple
WorkingDirectory=/opt/timescaledb
ExecStart=/usr/bin/docker compose up
ExecStop=/usr/bin/docker compose down
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target

$> sudo systemctl enable timescaledb.service
$> sudo systemctl start timescaledb.service

Install Joule
=============
$> sudo pip3 install joule
$> sudo joule admin initialize --dsn joule:joule@localhost:5432/joule

Install Lumen
=============
$> sudo mkdir /opt/lumen && cd /opt/lumen
$> wget https://raw.githubusercontent.com/wattsworth/lumen-docker/main/docker-compose.yml
$> wget https://raw.githubusercontent.com/wattsworth/lumen-docker/main/sample.env -O .env

# systemd service file
[Unit]
Description=Lumen
After=docker.service

[Service]
Type=simple
WorkingDirectory=/opt/lumen
ExecStart=/usr/local/bin/docker-compose up
ExecStop=/usr/local/bin/docker-compose down
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target

$> sudo systemctl enable lumen.service
$> sudo systemctl start lumen.service


Configure Nginx
===============

$> sudo apt-get install nginx -y
$> sudo rm /etc/nginx/sites-enabled/default
$> sudo wget https://github.com/wattsworth/lumen-docker/raw/master/nginx.conf -O /etc/nginx/sites-enabled/lumen.conf
$> sudo adduser www-data joule

