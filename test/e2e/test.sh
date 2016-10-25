#!/bin/bash
set -e
rm -rf /etc/joule || true
ln -s /src/test/e2e /etc/joule
apache2ctl start
python3 setup.py install > /dev/null
echo "----TEST START----"
sleep 1
exec /src/test/e2e/test.py
#exec jouled --config /etc/joule/main.conf
