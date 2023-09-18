#!/bin/bash

#update the certificates in PKI
cd pki
bash update_certs.sh
cd -

#Build the docker image
#echo "PRE: building docker image"
echo $PWD
docker compose --file timescale-docker-compose.yml up \
  --build --abort-on-container-exit --attach node1.joule --attach node2.joule

#CMD=/src/test/e2e/main_node.py
#CMD=/src/test/e2e/raw_jouled.sh
#docker run --rm jdonnal/joule:testing $CMD
#EXIT_CODE=$?

echo "POST: removing images and tmp files"
#docker rmi jdonnal/joule:testing >> /dev/null
docker rm `docker ps -a -q`
docker compose --file timescale-docker-compose.yml rm -f

exit $EXIT_CODE
