#!/bin/sh
# wait-for-postgres.sh

set -e

host="$1"
shift
cmd="$@"

# check if postgres is up on port 5432 without using the psql tool
until pg_isready -h "$host" -p 5432 -U "postgres"; do
  #>&2 echo "Postgres is unavailable - sleeping"
  sleep 1
done
cd /joule
# tried using coverage but the coverage report was empty (no lines covered)
exec $cmd
