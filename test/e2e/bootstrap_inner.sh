#!/bin/bash
set -e

CONF_FILE=/etc/joule/main.conf
apache2ctl start
#python3 setup.py install  >> /dev/null
rm -rf /etc/joule || true
ln -s /src/test/e2e /etc/joule
echo "running joule daemon"
exec jouled --config $CONF_FILE 

