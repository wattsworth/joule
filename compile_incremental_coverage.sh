#!/bin/bash
set -e

# copy the coverage files from coverage_partials
mv .coverage.* incremental_coverages
cp current_coverages/.coverage.* .
cp incremental_coverages/.coverage.* . 
coverage combine
coverage html
