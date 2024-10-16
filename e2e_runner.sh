#!/bin/bash
# run the e2e tests
cd tests/e2e 
./runner.sh
cd -

# consolidate the code coverage
coverage combine
coverage html