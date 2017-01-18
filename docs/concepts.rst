==============
Concepts
==============


.. _streams:

Streams
"""""""

Streams are timestamped data flows that connect modules together.
Streams can represent primary measurements such as readings from a current
sensor or derived measurements such as harmonic content. A stream has
one or more elements and can be viewed as a database table: 

 ========= ======== ======== === ========
 timestamp element1 element2 ... elementN
 ========= ======== ======== === ========
 1003421   0.0      10.5     ... 2.3
 1003423   1.0      -8.0     ... 2.3
 1003429   8.0      12.5     ... 2.3
 1003485   4.0      83.5     ... 2.3
 ========= ======== ======== === ========


.. _modules:

Modules
"""""""

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
"""""""
Using a light sensor and temperature sensor to detect occupancy in a room:

.. image:: /images/joule_system.png
