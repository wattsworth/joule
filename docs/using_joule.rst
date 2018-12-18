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

Joule is a system service. Use the ``joule`` command to interact with the service.

.. raw:: html

    <div class="bash-code">

    # joule is a systemd service
    $> sudo service joule restart

    # use journalctl to view joule logs
    $> sudo journalctl -u joule.service
    ... journalctl output

    # use the joule CLI to interact with the service
    $> joule info
    whatever is produced by joule info

    </div>

Joule constructs the pipeline based on configuration files in **/etc/joule**. Details on these
configuration files is provided in the sections below.

.. _sec-modules:

Module Configuration
--------------------

:ref:`modules` are executable programs managed by Joule. The module configuration format is shown below:

.. raw:: html

    <div class="config-file">

    : Module Configuration File

    [Main]
    #required settings (examples)
    exec_cmd = /path/to/module.py
    name = Processing Module

    #optional settings (defaults)
    description =
    has_interface = no

    [Arguments]
    arg = value
    #additional keyword arguments ...

    [Inputs]
    in1 = /stream/path/input1
    in2 = /stream/path/input2
    #additional inputs ...

    [Outputs]</span>
    out1 = /stream/path/output1
    out2 = /stream/path/output2
    #additional outputs ...

    </div>


Module configuration files must end with the **.conf** suffix and should be placed in
**/etc/joule/module_configs**. See the list below for information on each setting.
Only the **[Main]** section is required, other sections should be included as necessary.

**[Main]**
  * ``exec_cmd`` -- path to module executable, may include command line arguments
  * ``name`` -- module name
  * ``description`` -- optional module description
  * ``has_interface`` -- whether the module has a web interface

**[Arguments]**
  * ``key = value`` -- keyword arguments (these may also be specified in the ``exec_cmd``)

**[Inputs]**
  * ``name = /stream/path`` -- input :ref:`sec-pipes`

**[Outputs]**
  * ``name = /stream/path`` -- output pipe configuration

Note: Reader Modules may only have a single output and no inputs. Filter modules have no restrictions on the number
of inputs and outputs.

.. _sec-pipes:

Pipe Configuration
------------------

:ref:`pipes` connect modules to streams and are configured in the **[Inputs]** and **[Outputs]** section of the :ref:`sec-modules`
file. At a minimum the configuration specifies a pipe name and a stream path shown in Example 1 below.

.. raw:: html

    <div class="config-file">

    : Pipe Configuration Format

    #1. basic configuration [pipe name] = [stream path]
    simple = /stream/path/simple

    #2. with inline stream configuration
    inline = /stream/path/inline:float32[x,y,z]

    #3. remote connection, must include inline stream config
    remote = node2.net:8088 /stream/path/remote:float32[x,y,z]

    </div>

The pipe configuration can also include an inline stream configuration. This can be used in place of a :ref:`sec-streams`
file or in addition to it. Using both enables static type checking for the pipeline. The inline configuration is
separated from the stream path by a colon ``:``. The stream datatype is followed by a list of comma separated element names
enclosed with brackets ``[ ]``. If
the stream is not explicitly configured or does not already exist in the database it is created with default
attributes. In Example 2 above the ``inline`` pipe is connected to ``/stream/path/inline``
which has three ``float32`` elements named ``x``, ``y``, and ``z``. If this stream already exists
with a different datatype or number of elements, Joule will not start the module.

Pipes can also connect to remote streams. To specify a remote source or destination add the URL and optional port
number before the stream path. The URL is separated from the stream path by a single space. Remote pipes must include an inline stream configuration.
In example 3 above the ``remote`` pipe is connected to ``/stream/path/remote`` on ``node2.net``. If this stream does not
exist on **node2**, it will be created with default attributes. If it does exist with a different datatype, or number of
elements, Joule will not start the module.

Streams can be connected to multiple input pipes but may only be connected to a single output pipe. If a module
attempts to connect an output pipe to a stream that already has a producer, Joule will not start the module.

.. _sec-streams:

Stream Configuration
--------------------

Streams are timestamped data flows. They are composed of one or more elements as shown
below. Timestamps are in Unix microseconds (elapsed time since January 1, 1970).

 ========= ======== ======== === ========
 Timestamp Element1 Element2 ... ElementN
 ========= ======== ======== === ========
 1003421   0.0      10.5     ... 2.3
 1003423   1.0      -8.0     ... 2.3
 1003429   8.0      12.5     ... 2.3
 1003485   4.0      83.5     ... 2.3
 ...       ...      ...      ... ...
 ========= ======== ======== === ========

The configuration format is shown below:

.. raw:: html

  <div class="config-file">

  : Stream Configuration File

  [Main]
  #required settings (examples)
  name = stream name
  path = /stream/path
  datatype = float32
  keep = 1w

  #optional settings (defaults)
  decimate = yes

  [Element1]
  #required settings (examples)
  name         = stream name

  #optional settings (defaults)
  plottable    = yes
  discrete     = no
  offset       = 0.0
  scale_factor = 1.0
  default_max  =
  default_min  =

  #additional elements...

  </div>

Stream configuration files must end with the **.conf** suffix and should be placed in
**/etc/joule/stream_configs**. Both **[Main]** and **[Element1]** are required.
For streams with more than one element include additional sections **[Element2]**, **[Element3]**, etc.
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
    For example ``6d`` will keep the last six days of data. Specify ``none``
    to keep no data or ``all`` to keep all data.

  * ``decimate`` -- whether decimated data will be stored for this stream. Decimation
    roughly doubles the required storage but enables web UI visualization.

**[Element#]**
  * ``name`` -- element identifier, may contain whitespace
*NOTE:* the following settings apply only to visualizations in the web UI
  * ``plottable`` -- **[yes|no]** whether the element can be plotted
  * ``type`` -- **[continuous|discrete|event]** controls the plot type
  * ``offset``-- apply linear scaling **y=scale_factor\*(x-offset)**
  * ``scale_factor``-- apply linear scaling **y=scale_factor\*(x-offset)**
  * ``default_max``-- control axis scaling, leave blank to auto scale
  * ``default_min``-- control axis scaling, leave blank to auto scale

Streams may also be configured using an abbreviated inline syntax in a module's :ref:`sec-pipes`.
  
.. _sec-system-configuration:

System Configuration
--------------------

Joule uses a set of default configurations that should work for most
cases. These defaults can be customized by editing
**/etc/joule/main.conf**. Start joule with the **--config** flag to use a configuration file at
an alternate location. The example **main.conf** below shows the
full set of options and their default settings:

.. raw:: html

  <div class="config-file">

  : /etc/joule/main.conf

  #default settings shown
  [Main]
  IPAddress = 0.0.0.0
  Port = 8088
  NilmdbURL = http://localhost/nilmdb
  Database = joule@localhost:5438/joule
  InsertPeriod = 5
  CleanupPeriod = 60
  MaxLogLines = 100
  ModuleDirectory = /etc/joule/module_configs
  StreamDirectory = /etc/joule/stream_configs

  </div>

See the list below for information on each setting.

``NilmDB``
  * ``url`` -- address of NilmDB server
  * ``InsertionPeriod`` -- how often to send stream data to NilmDB (in seconds)
  * ``CleanupPeriod`` -- how often to remove old data as specified by stream **keep** parameters
``ProcDB``
  * ``DbPath`` -- path to sqlite database used internally by joule
  * ``MaxLogLines`` -- max number of lines to keep in a module log file (automatically rolls)
``Jouled``
  * ``ModuleDirectory`` -- folder with module configuration files (absolute path)
  * ``StreamDirectory`` -- folder with stream configuration files (absolute path)
  * ``ModulesDocs`` -- JSON data file for module documentation
  * ``IPAddress`` -- address to listen for standalone modules
  * ``Port`` -- port to listen for standalone modules
