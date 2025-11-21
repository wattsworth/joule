#!/bin/bash
set -e

# run the unittests (install pytest pytest-xdist pytest-cov )
#pytest --cov=joule tests/ -n auto -x
coverage run -m unittest discover -f

# run the e2e tests
cd tests/e2e 
./runner.sh
cd -

# flush all of the coverage information
rm -f current_coverages/.coverage*
rm -f incremental_coverages/.coverage*
cp .coverage.* current_coverages

# consolidate the code coverage
coverage combine
coverage xml
coverage html

# remove test artifacts
rm -f postgres-data

echo "SKIPPING SONAR SCAN"
exit 1

# run sonar scan and upload results
SONAR_TOKEN=$(cat sonar.apikey)

docker run \
--rm \
-e SONAR_HOST_URL="https://sonarcloud.io"  \
-e SONAR_TOKEN="${SONAR_TOKEN}" \
-v ".:/usr/src" \
sonarsource/sonar-scanner-cli