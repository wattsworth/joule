#!/bin/bash


#Build the docker image
echo "PRE: building docker image"
docker build ../.. -f Dockerfile -t jdonnal/joule:testing  >> /dev/null

#docker-compose up --abort-on-container-exit
docker-compose run  --rm testbed
echo "POST: removing images and tmp files"
docker-compose stop -t 1 sut >> /dev/null
docker rm `docker ps -a -q` >> /dev/null
docker volume rm `docker volume ls -q -f "dangling=true"` >> /dev/null
#docker volume rm `docker volume ls -q` >> /dev/null
