#!/bin/bash
set -e
apt update
#add the PostgreSQL third party repository to get the latest PostgreSQL packages
apt install gnupg postgresql-common apt-transport-https lsb-release wget -y
# Run the PostgreSQL repository setup script:
sh /usr/share/postgresql-common/pgdg/apt.postgresql.org.sh
# Ubuntu
echo "deb https://packagecloud.io/timescale/timescaledb/ubuntu/ $(lsb_release -c -s) main" | sudo tee /etc/apt/sources.list.d/timescaledb.list
wget --quiet -O - https://packagecloud.io/timescale/timescaledb/gpgkey | sudo gpg --dearmor -o /etc/apt/trusted.gpg.d/timescaledb.gpg
apt update
apt install timescaledb-2-postgresql-15 -y
timescaledb-tune --quiet --yes

apt install postgresql-client-15 -y
systemctl restart postgresql
sudo -u postgres psql