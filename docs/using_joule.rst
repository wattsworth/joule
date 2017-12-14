.. _using-joule:

Using Joule
===========


Joule decentralizes signal processing into discrete **modules**. These
modules are connected by **streams** as shown in the figure below. The
interconnection of modules and streams form a data **pipeline**. A pipeline may execute
as a single proces, a collection of processes, or even be distributed
across multiple nodes in a network without adjusting any module code.

.. figure:: /images/data_pipeline.png

   Joule **pipelines** are composed of **modules** and **streams**

Joule constructs the pipeline based on module and stream configuration files.
Files must end with the **.conf** suffix and by default should be placed in
**/etc/joule/module_configs** and **/etc/joule/stream_configs** respectively.
The pipeline must form a directed acyclic graph (DAG). Circular paths are
not allowed.

Modules
-------

Modules are executable programs. Joule runs each module as a separate
process. This enfores isolation and improves resiliency.
Malfunctioning modules do not affect other parts of the pipeline
and can be restarted without interrupting the data flow.

The module configuration format is shown below:

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


See the list below for information on each setting.

**[Main]**
  * ``exec_cmd`` -- path to module executable. This can include command line arguments
  * ``name`` -- identifies the module in Joule CLI output
  * ``description`` -- optional description used in Joule CLI output

**[Inputs]**
  * ``name = /stream/path`` -- association between module input and data stream

**[Outputs]**
  * ``name = /stream/path`` -- association between module output and data stream

The input and output **names** should be provided by the module author.
Inputs may be reused between modules, but
outputs must be unique. All input and output
**streams** must have corresponding configuration files.

Streams
-------
Streams are timestamped data flows that connect modules.
Streams can be visualized as a tabular data
structure. Timestamps are in Unix microseconds (elapsed time since
January 1, 1970).

 ========= ======== ======== === ========
 Timestamp Element1 Element2 ... ElementN
 ========= ======== ======== === ========
 1003421   0.0      10.5     ... 2.3
 1003423   1.0      -8.0     ... 2.3
 1003429   8.0      12.5     ... 2.3
 1003485   4.0      83.5     ... 2.3
 ...       ...      ...      ... ...
 ========= ======== ======== === ========

The stream configuration format is shown below:

.. raw:: html

  <div class="header ini">
  Stream Configuration File
  </div>
  <div class="code ini"><span>[Main]</span>
  <i>#required settings (examples)</i>
  <b>name</b> = stream name
  <b>path</b> = /stream/path
  <b>datatype</b> = float32
  <b>keep</b> = 1w
  <i>#optional settings (defaults)</i>
  <b>decimate</b> = yes

  <span>[Element1]</span>
  <i>#required settings (examples)</i>
  <b>name</b>         = stream name
  <i>#optional settings (defaults)</i>
  <b>plottable</b>    = yes
  <b>discrete</b>     = no
  <b>offset</b>       = 0.0
  <b>scale_factor</b> = 1.0
  <b>default_max</b>  =
  <b>default_min</b>  =

  <i>#additional elements...</i>
  </div>

See the list below for information on each setting.

**[Main]**
  * ``name`` -- stream identifier, white space is permitted
  * ``path`` -- unique identifier which follows the Unix file naming convention. The web UI
    visualizes the path as a folder hierarchy.
  * ``datatype`` -- element datatype, must be one of the following values:

    .. csv-table::
      :align: center

      float32, int8, uint8
      float64, int16, uint16
      ,        int32, uint32
      ,        int64, uint64

  * ``keep`` -- how long to store stream data. Format is a value and unit.
      Units are **h**: hours, **d**: days, **w**: weeks, **m**: months, **y**: years.
      For example ``6d`` will keep the last six days of data. A value of ``false``
      means no data will be stored for this stream.

  * ``decimate`` -- whether decimated data will be stored for this stream. Decimation
    roughly doubles the required storage but enables web UI visualization.

**[Element#]**
  * ``name`` -- element identifier, may contain whitespace
      *NOTE:* the following settings apply to visualizations in the web UI
  * ``plottable`` -- **[yes|no]** whether the element can be plotted
  * ``type`` -- **[continuous|discrete|event]** controls the plot type
  * ``offset``-- apply linear scaling to data visualization **y=scale_factor\*(x-offset)**
  * ``scale_factor``-- apply linear scaling to data visualization **y=scale_factor\*(x-offset)**
  * ``default_max``-- control axis scaling, leave blank to auto scale
  * ``default_min``-- control axis scaling, leave blank to auto scale



Command Line Interface
----------------------

``jouled`` -- controls pipeline execution, runs as a system daemon

  .. raw:: html

    <div class="header bash">
    Command Line:
    </div>
    <div class="code bash"><i># use service to control jouled:</i>
    <i># NOTE: restart the service to apply configuration file changes</i>
    <b>$>sudo service jouled</b> [start|stop|restart|status]

    <i># by default jouled starts at boot, this can be enabled or disabled:</i>
    <b>$>sudo systemctl</b> [enable|disable] <b>jouled.service</b>

    <i># jouled may be run in the foreground if the service is stopped</i>
    <b>$> sudo jouled</b>
    <i># exit with Ctrl-C</i>
    </div>

``joule modules`` -- view currently executing modules

  .. raw:: html

      <div class="header bash">
      Command Line:
      </div>
      <div class="code bash"><b>$>joule modules</b>
      +-------------+--------------+----------------+---------+-----+
      | Module      | Sources      | Destinations   | Status  | CPU |
      +-------------+--------------+----------------+---------+-----+
      | Demo Reader |              | /demo/random   | running | 0%  |
      | Demo Filter | /demo/random | /demo/smoothed | running | 0%  |
      +-------------+--------------+----------------+---------+-----+
      </div>


``joule logs`` -- view stdout and stderr from a module

  Joule keeps a rolling log of module output. By default the last 100 lines
  are stored, this can be configured in :ref:`main.conf`

  .. raw:: html

      <div class="header bash">
      Command Line:
      </div>
      <div class="code bash"><b>$>joule logs "Demo Filter"</b>
      [27 Jan 2017 18:22:48] ---starting module---
      [27 Jan 2017 18:22:48] Starting moving average filter with window size 9
      #... additional output
      </div>


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
