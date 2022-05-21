#!/bin/sh
# wait-for-postgres.sh

set -e

host="$1"
shift
cmd="$@"

echo "Waiting for Postgres..."
until PGPASSWORD=$POSTGRES_PASSWORD psql -h "$host" -U "postgres" -c '\q'; do
  echo "Postgres is unavailable - sleeping"
  sleep 3
done
echo "Postgres is up - executing command"
exec $cmd
