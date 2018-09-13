.. _quick-start:

===========
Quick Start
===========

Joule is part of the Wattsworth software stack. See
http://wattsworth.net/install.html for installation details. Before continuing
make sure Joule is installed and the jouled service is running:


.. raw:: html

  <div class="header bash">
  Command Line:
  </div>
  <div class="code bash">
  <i># ensure the joule CLI is installed</i>
  <b>$> joule --version</b>
  joule, version 0.9

  <i># confirm the local joule server is running</i>
  <b>$> joule info</b>
  Server Version: 0.9
  Status: online

  </div>
  
This guide will step through the implementation of the three stage pipeline shown below:

.. image:: /images/getting_started_pipeline.png


The Data Source
---------------

The first module is a data reader. Reader modules "read" data into the
Joule pipeline. This data can come from embedded sensors, HTTP API's,
system logs, or any other timeseries data source.

Our reader will simply produce random values.  Joule provides a
built-in module specifically for this purpose. Stubbing pipeline
inputs with a random data source can simplify unit testing and expose
logic errors.  See the `Module Documentation`_ page
for more details on this and other Joule modules.

.. _Module Documentation: /modules


Try out **random** on the command line:

.. raw:: html

  <div class="header bash">
  Command Line:
  </div>
  <div class="code bash"><b>$> joule-random-reader -h</b>
  <i>#  ... module documentation (available at http://docs.wattsworth.net/modules)</i>

  <b>$> joule-random-reader --width 2 --rate 10</b>
  1485188853650944 0.32359053067687582 0.70028608966895545
  1485188853750944 0.72139550945715136 0.39218791387411422
  1485188853850944 0.40728044378612194 0.26446072057019654
  1485188853950944 0.61021957330250398 0.27359526775709841
  <i># output continues, hit ctrl-c to stop </i>

  </div>

Now let's add this module to our pipeline. We need to create a :ref:`sec-modules` file
to tell Joule how to execute the module and where
to connect its output. To do this create the following file:


.. raw:: html

  <div class="header ini">
  /etc/joule/module_configs/my_reader.conf
  </div>
  <div class="code ini"><span>[Main]</span>
  <b>exec_cmd =</b> joule-random-reader
  <b>name =</b> Data Source

  <span>[Arguments]</span>
  <b>width = </b>2
  <b>rate  = </b>10

  <span>[Outputs]</span>
  <b>output =</b> /demo/random:float32[x,y]
  </div>

This connects the module to the stream **/demo/random**. The stream is configured
inline after the colon (:). This specifies a **float32** datatype and two elements named
**x** and **y**. To control other stream options create a :ref:`sec-streams` file
in **/etc/joule/stream_configs**. Now the pipeline is ready to execute. Restart joule and check that the
new module is running:

.. raw:: html

  <div class="header bash">
  Command Line:
  </div>
  <div class="code bash"><i># restart joule to use the new configuration files</i>
  <b>$> sudo systemctl joule.service restart</b>

  <i># check pipeline status using the joule CLI</i>
  <b>$> joule module list</b>
  ╒═════════════╤══════════╤══════════════╤═════════╤═════════════╕
  │ Name        │ Inputs   │ Outputs      │   CPU % │   Mem (KiB) │
  ╞═════════════╪══════════╪══════════════╪═════════╪═════════════╡
  │ Data Source │          │ /demo/random │       0 │       62868 │
  ╘═════════════╧══════════╧══════════════╧═════════╧═════════════╛

  <i># check module logs for any errors</i>
  <b>$> joule module logs "Data Source"</b>
  [2018-09-12T15:51:38.845242]: ---starting module---


  <i># confirm the pipeline is producing data</i>
  <b>$> joule stream info /demo/random</b>
        Name:         random
        Description:  —
        Datatype:     float32
        Keep:         all data
        Decimate:     yes

        Status:       ● [active]
        Start:        2018-09-12 15:51:39.811572
        End:          2018-09-12 15:52:59.711573
        Rows:         800

    ╒════════╤═════════╤════════════╤═══════════╕
    │  Name  │  Units  │  Display   │  Min,Max  │
    ╞════════╪═════════╪════════════╪═══════════╡
    │   x    │    —    │ continuous │   auto    │
    ├────────┼─────────┼────────────┼───────────┤
    │   y    │    —    │ continuous │   auto    │
    ╘════════╧═════════╧════════════╧═══════════╛

  </div>

The Data Processor
------------------

Now let's add a filter to smooth out the random data produced by the
reader. Joule provides a built-in moving average filter, **mean**,
that does exactly this.  See the `Module Documentation`_ page
for more details on this and other Joule modules.

Joule filters can execute as standalone programs but require extra
configuration to do so because they can have multiple inputs and
outputs. For now let's just run it in the Joule environment. To add
the module to the pipeline create the following file:

.. raw:: html

  <div class="header ini">
  /etc/joule/module_configs/demo_filter.conf
  </div>
  <div class="code ini"><span>[Main]</span>
  <b>exec_cmd =</b> joule-mean-filter
  <b>name =</b> Data Processor

  <span>[Arguments]</span>
  <b>window =</b> 11
  
  <span>[Inputs]</span>
  <b>input =</b> /demo/random

  <span>[Outputs]</span>
  <b>output =</b> /demo/smoothed:float32[x,y]
  </div>

The input stream is already configured by the producer module. The output will have the same
datatype and number of elements. Now the pipeline is fully configured.  Restart joule and check that
both modules are running:

.. raw:: html

  <div class="header bash">
  Command Line:
  </div>
  <div class="code bash"><i># restart joule to use the new configuration files</i>
  <b>$> sudo systemctl joule.service restart</b>

  <i># check pipeline status using the joule CLI</i>
  <b>$> joule module list</b>
  ╒════════════════╤══════════════╤════════════════╤═════════╤═════════════╕
  │ Name           │ Inputs       │ Outputs        │   CPU % │   Mem (KiB) │
  ╞════════════════╪══════════════╪════════════════╪═════════╪═════════════╡
  │ Data Processor │ /demo/random │ /demo/smoothed │       0 │       63880 │
  ├────────────────┼──────────────┼────────────────┼─────────┼─────────────┤
  │ Data Source    │              │ /demo/random   │       0 │       63172 │
  ╘════════════════╧══════════════╧════════════════╧═════════╧═════════════╛

  <b>$> joule logs "Data Processor"</b>
  [2018-09-12T16:00:34.298364]: ---starting module---

  <i># confirm the pipeline is producing data (check /demo/random as well)</i>
  <b>$> joule stream info /demo/smoothed</b>

        Name:         smoothed
        Description:  —
        Datatype:     float32
        Keep:         all data
        Decimate:     yes

        Status:       ● [active]
        Start:        2018-09-12 16:00:35.788668
        End:          2018-09-12 16:02:29.688669
        Rows:         1140

    ╒════════╤═════════╤════════════╤═══════════╕
    │  Name  │  Units  │  Display   │  Min,Max  │
    ╞════════╪═════════╪════════════╪═══════════╡
    │   x    │    —    │ continuous │   auto    │
    ├────────┼─────────┼────────────┼───────────┤
    │   y    │    —    │ continuous │   auto    │
    ╘════════╧═════════╧════════════╧═══════════╛

  </div>

The User Interface
------------------

Now let's add a user interface to complete the pipeline.
 Joule provides a built-in
 visualizer module.  See the `Module Documentation`_ page
for more details on this and other Joule modules.

Add the following file to the configuration directory to add the
module to the pipeline.

.. raw:: html

  <div class="header ini">
  /etc/joule/module_configs/user_interface.conf
  </div>
  <div class="code ini"><span>[Main]</span>
  <b>exec_cmd =</b> joule-visualizer-filter
  <b>name =</b> User Interface
  <b>has_interface =</b> yes

  <span>[Arguments]</span>
  <b>title =</b> Quick Start Data Pipeline

  <span>[Inputs]</span>
  <b>smoothed =</b> /demo/smoothed
  <b>random =</b> /demo/random
  </div>

The URL of the interface is available in the module info:

.. raw:: html

    <div class="header bash">
    Command Line:
    </div>
    <div class="code bash"><i># restart joule to use the new configuration files</i>
    <b>$> sudo systemctl joule.service restart</b>

    <i># check pipeline status using the joule CLI</i>
    <b>$> joule module list</b>
    ╒════════════════╤════════════════╤════════════════╤═════════╤═════════════╕
    │ Name           │ Inputs         │ Outputs        │   CPU % │   Mem (KiB) │
    ╞════════════════╪════════════════╪════════════════╪═════════╪═════════════╡
    │ Data Processor │ /demo/random   │ /demo/smoothed │       2 │       63924 │
    ├────────────────┼────────────────┼────────────────┼─────────┼─────────────┤
    │ User Interface │ /demo/smoothed │                │       0 │       64548 │
    │                │ /demo/random   │                │         │             │
    ├────────────────┼────────────────┼────────────────┼─────────┼─────────────┤
    │ Data Source    │                │ /demo/random   │       0 │       62748 │
    ╘════════════════╧════════════════╧════════════════╧═════════╧═════════════╛

    <i># check the module info to find the interface URL</i>
    <b>$> joule module info "User Interface"</b>
    Name:
        User Interface
    Description:

    Interface URL:
        http://localhost:8088/interface/1/
    Inputs:
        smoothed: /demo/smoothed
        random: /demo/random
    Outputs:
        --none--
    </div>

Open a browser and navigate to the specified URL to view the interface.


Next Steps
----------

For more details on modules and streams read :ref:`using-joule` or
visit the `Lumen Documentation`_ to start visualizing your data.

.. _Lumen Documentation: /lumen/getting_started.html

