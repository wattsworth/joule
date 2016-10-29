#!/bin/bash


#Build the docker image
echo "PRE: building docker image"
docker build ../.. -f Dockerfile -t jdonnal/joule:testing  >> /dev/null


CMD=/src/test/e2e/bootstrap_inner.py
docker run --rm jdonnal/joule:testing $CMD
EXIT_CODE=$?

echo "POST: removing images and tmp files"
#docker rmi jdonnal/joule:testing >> /dev/null

exit $EXIT_CODE
