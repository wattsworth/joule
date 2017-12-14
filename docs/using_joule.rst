.. _using-joule:

Using Joule
===========

Framework overview


Modules
-------


.. raw:: html

  <div class="header ini">
  Module Configuration File
  </div>
  <div class="code ini"><span>[Main]</span>
  <i>#required settings (examples)</i>
  <b>exec_cmd =</b> /path/to/module.py --args
  <b>name =</b> Processing Module
  <i>#optional settings (defaults)</i>
  <b>description =</b>

  <span>[Inputs]</span>
  <b>in1 =</b> /stream/path/input1
  <b>in2 =</b> /stream/path/input2
  <i>#additional inputs ... </i>

  <span>[Outputs]</span>
  <b>out1 =</b> /stream/path/output1
  <b>out2 =</b> /stream/path/output2
  <i>#additional outputs ... </i>

  </div>



Streams
-------
Streams are timestamped data flows that connect modules.
Streams can be visualized as an infinite tabular data
structure as shown below:

 ========= ======== ======== === ========
 timestamp element1 element2 ... elementN
 ========= ======== ======== === ========
 1003421   0.0      10.5     ... 2.3
 1003423   1.0      -8.0     ... 2.3
 1003429   8.0      12.5     ... 2.3
 1003485   4.0      83.5     ... 2.3
 ...       ...      ...      ... ...
 ========= ======== ======== === ========

Timestamps are in Unix microseconds (elapsed time since
January 1, 1970). The elements are homogenously typed. Valid
types are listed in the table below:

.. csv-table:: Element Datatypes
  :align: center

  float32, int8, uint8
  float64, int16, uint16
  ,        int32, uint32
  ,        int64, uint64

Streams are configured with the INI file format shown below.
Stream configure files must end with the *.conf suffix and be placed
in ``/etc/joule/stream_configs``.

.. raw:: html

  <div class="header ini">
  Stream Configuration File
  </div>
  <div class="code ini"><span>[Main]</span>
  <i>#required settings (examples)</i>
  <b>path</b> = /nilmdb/path/name
  <b>datatype</b> = float32
  <b>keep</b> = 1w
  <i>#optional settings (defaults)</i>
  <b>name</b> = custom title
  <b>decimate</b> = yes

  <span>[Element1]</span>
  <i>#required settings (examples)</i>
  <b>name</b>         = Element Name
  <i>#optional settings (defaults)</i>
  <b>plottable</b>    = yes
  <b>discrete</b>     = no
  <b>offset</b>       = 0.0
  <b>scale_factor</b> = 1.0
  <b>default_max</b>  = null
  <b>default_min</b>  = null
  <i>#additional elements...</i>
  </div>

NilmDB CLI
''''''''''

If the stream is persisted (keep value is not false) the data is stored
to NilmDB. The following commands are useful tools for managing
persisted streams.

* ``nilmtool list -n``
* ``nilmtool list -En /stream/path``
* ``nilm-copy /source/path /dest/path``
* ``nilmtool remove -s min -e max /stream/path``
* ``nilmtool destroy -R /stream/path``

Command Line Interface
----------------------
Start and stop joule

joule modules

joule logs


System Configuration
--------------------

Joule uses a set of default configurations that should work for most
cases. These defaults can be customized by editing
**/etc/joule/main.conf**. Start joule with the **--config** flag to use a configuration file at
an alternate location. The example **main.conf** below shows the
full set of options and their default settings:

.. raw:: html

  <div class="header ini">
  /etc/joule/main.conf
  </div>
  <div class="code ini"><i>#default settings shown</i>
  <span>[NilmDB]</span>
  <b>url =</b> http://localhost/nilmdb
  <b>InsertionPeriod =</b> 5

  <span>[ProcDB]</span>
  <b>DbPath =</b> /tmp/joule-proc-db.sqlite
  <b>MaxLogLines =</b> 100

  <span>[Jouled]</span>
  <b>ModuleDirectory =</b> /etc/joule/module_configs
  <b>StreamDirectory =</b> /etc/joule/stream_configs
  </div>

See the list below for information on each setting.

``NilmDB``
  * ``url`` -- address of NilmDB server
  * ``InsertionPeriod`` -- how often to send stream data to NilmDB (in seconds)
``ProcDB``
  * ``DbPath`` -- path to sqlite database used internally by joule
  * ``MaxLogLines`` -- max number of lines to keep in a module log file (automatically rolls)
``Jouled``
  * ``ModuleDirectory`` -- folder with module configuration files (absolute path)
  * ``StreamDirectory`` -- folder with stream configuration files (absolute path)
