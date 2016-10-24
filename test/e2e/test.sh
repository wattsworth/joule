#!/bin/bash
set -e
rm -rf /etc/joule || true
ln -s /src/test/e2e /etc/joule
python3 setup.py install > /dev/null
echo "---waiting 2 sec for joule boot---"
echo "----TEST START----"
joule status
echo "----TEST END----"
exit 2
