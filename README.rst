.. image:: https://coveralls.io/repos/github/wattsworth/joule/badge.svg?branch=master
  :target: https://coveralls.io/github/wattsworth/joule?branch=master

Joule
========

Joule is a data capture and signal processing engine. It allows you to build
robust sensors using embedded systems such as the
Raspberry Pi. Joule uses modules to build complex acquisition
and signal processing workflows from simple building blocks. 
Modules are user defined processes that are connected
together by data streams.

Joule acts as a process manager, ensuring that modules start at system
boot and are restarted if they fail. Joule also collects runtime
statistics and logs for each module making it easy to detect
bugs and find bottlenecks in processing pipelines.

See https://wattsworth.net/joule for full documentation. To get started see:
https://wattsworth.net/joule/quick_start.html

Streams
-------

Streams are timestamped data flows that connect modules together.
Streams can represent primary measurements such as readings from a current
sensor or derived measurements such as harmonic content. A stream has
one or more elements and can be viewed as a database table: ::

 ========= ====== ====== === ======
 timestamp value1 value2 ... valueN
 ========= ====== ====== === ======
 1003421   0.0    10.5   ... 2.3
 1003423   1.0    -8.0   ... 2.3
 1003429   8.0    12.5   ... 2.3
 1003485   4.0    83.5   ... 2.3
 ========= ====== ====== === ======



Modules
-------

Modules process streams. A module may receive zero, one or more
input streams and may produce zero, one, or more output streams. While
Joule does not enforce any structure on modules, we suggest
structuring your data pipeline with two types of modules: Readers, and
Filters. Readers take no inputs. They directly manage a sensor (eg a
TTY USB device) and generate an output data stream with sensor
values. Filters take these streams as inputs and produce new outputs.
Filters can be chained to produce complex behavior from simple,
reusable building blocks.


Example
-------
Using a light sensor and temperature sensor to detect occupancy in a room: ::

    [Module]  a_stream
    
    [ TempReader] --> temp_values  --,
    [LightReader] --> light_values --+--> [OccupancyFilter] --> room_status

Features
--------

- Fast, lightweight
- Highbandwidth signal processing

Installation
------------

Joule requires Python 3.10 or later. Install Joule by running:

  $> pip install -r requirements.txt
  $> pip install .

It is also available through PyPi:

  $> python3 -m pip install joule

To run the Joule daemon, you must have a PostgreSQL database running with the TimescaleDB extension installed.
Full instructions on installing TimescaleDB can be found at https://docs.timescale.com/latest/getting-started/installation
A script to automate the installation process on Ubuntu is included in this repository:

  $> sudo ./install-postgresql.sh

A script to create a database with the TimescaleDB extension is also included:

  $> sudo -u postgres psql < ./postgresql-bootstrap.sql

NOTE: It is strongly recommended to change the default password in the bootstrap script before running it.
Once the database has been configured you can initialize Joule using the appropriate DSN string:

  $> sudo joule admin initialize --dsn joule:joule@localhost:5432/joule

Change the password to match your configuration.
Finally, use systemctl to manage the daemon service:

  $> sudo systemctl [enable|disable|start|stop|status] joule

To connect to the Joule daemon, use the command line client:

  $> sudo -E joule admin authorize

See https://wattsworth.net/joule for full documentation on using Joule.

Tests
-----

To run unittests and collect coverage information:

    $> coverage run -m unittest
    $> coverage html
    $> python3 -m http.server --directory htmlcov

To run integration tests you must have Docker and access to the nilmdb image (for nilmdb tests)

    $ joule/tests/e2e> ./runner.sh [timescale|nilmdb]



