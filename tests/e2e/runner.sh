#!/bin/bash
set -e
#update the certificates in PKI
cd pki
bash update_certs.sh
cd -


docker compose --file timescale-docker-compose.yml up \
  --build --abort-on-container-exit --attach node1.joule --attach node2.joule


echo "POST: removing images and tmp files"
docker compose --file timescale-docker-compose.yml rm -f
docker image rm e2e-node2.joule
docker image rm e2e-node1.joule
exit $EXIT_CODE
