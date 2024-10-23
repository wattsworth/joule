#!/bin/bash
# wait-for-postgres.sh

set -e

host="$1"
# if host is timescale, then set node_name to node1
if [ "$host" = "timescale" ]; then
  nodename="node1.joule"
else
  nodename="node2.joule"
fi



# start nginx, but not jouled
./runner.sh --nginx-only

# check if postgres is up on port 5432 without using the psql tool
until pg_isready -h "$host" -p 5432 -U "postgres" > /dev/null; do
  #>&2 echo "Postgres is unavailable - sleeping"
  sleep 1
done
source /venv/bin/activate
cd /joule
pip install -e . > /dev/null
cp /joule/tests/e2e/stub_systemctl.sh /usr/local/bin/systemctl
chmod +x /usr/local/bin/systemctl

coverage run --rcfile=/joule/.coveragerc -m joule.cli admin initialize --dsn postgres:password@$host:5432/postgres --name $nodename --bind=0.0.0.0 --port=8080 --generate-user-file
cat /tmp/systemctl.log

#TODO is this needed?
export COVERAGE_FILE=/joule/.coverage

shift
cmd="$@"
exec $cmd
