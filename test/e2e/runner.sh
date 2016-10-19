#!/bin/bash

CODE_DIR=/home/jdonnal/joule
SOURCE=$CODE_DIR/joule:/joule
TEST=$CODE_DIR/test/e2e/:/etc/joule

VOLUMES="-v $SOURCE -v $TEST"
docker run -it --rm $VOLUMES jdonnal/joule /etc/joule/bootstrap_inner.sh
