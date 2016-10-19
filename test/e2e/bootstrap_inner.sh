#!/bin/bash
set -e

CONF_FILE=/etc/joule/main.conf
apache2ctl start
cd /
python3 -m joule.daemon.daemon --config $CONF_FILE
