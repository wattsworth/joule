#!/bin/bash

apache2ctl start
nilmdb-server -p 80 -d /opt/data
