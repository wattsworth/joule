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

Joule requires Python 3.5 or later. Install Joule by running:

  python setup.py install

See Installing Joule for more information.  

Contribute
----------

- Issue Tracker: https://git.wattsworth.net/wattsworth/joule/issues
- Source Code: https://git.wattsworth.net/wattsworth/joule.git

Support
-------

If you are having issues, please let us know.
E-mail donnal@usna.edu

License
-------

Full copyright is retained by the project creators.If you are
interested in using this code contact donnal@usna.edu for licensing
options.

