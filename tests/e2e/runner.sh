#!/bin/bash


#Build the docker image
#echo "PRE: building docker image"
#docker build ../.. -f Dockerfile -t jdonnal/joule:testing  >> /dev/null
docker-compose up --build --abort-on-container-exit 

#CMD=/src/test/e2e/bootstrap_inner.py
#CMD=/src/test/e2e/raw_jouled.sh
#docker run --rm jdonnal/joule:testing $CMD
#EXIT_CODE=$?

echo "POST: removing images and tmp files"
#docker rmi jdonnal/joule:testing >> /dev/null
docker rm `docker ps -a -q`
docker-compose rm -f

exit $EXIT_CODE
