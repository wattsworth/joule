#!/bin/bash


#Build the docker image
echo "PRE: building docker image"
docker build ../.. -f Dockerfile -t jdonnal/joule:testing  >> /dev/null


CMD=/src/test/e2e/bootstrap_inner.py
docker run jdonnal/joule:testing $CMD
EXIT_CODE=$?

echo "POST: removing images and tmp files"
docker rm `docker ps -a -q` >> /dev/null
docker volume rm `docker volume ls -q -f "dangling=true"` >> /dev/null
exit $EXIT_CODE
