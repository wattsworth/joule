#!/bin/bash

SOURCE_DIR="/src"
SCENARIO_DIR="/src/test/e2e/scenarios"
MODULE_SCRIPT_DIR="/src/test/e2e/module_scripts"
JOULE_CONF_DIR="/etc/joule"

apache2ctl start
ln -s $MODULE_SCRIPT_DIR /module_scripts
cd $SOURCE_DIR
python3 setup.py install
rm -rf $JOULE_CONF_DIR
ln -s /src/test/e2e/scenarios/basic_operation /etc/joule
exec jouled
