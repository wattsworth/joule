.. _getting-started:

===============
Getting Started
===============

Joule is part of the Wattsworth software stack. See
http://wattsworth.net/install.html for installation details. Before continuing
make sure Joule is installed and the database is accessible:


.. raw:: html

  <div class="header bash">
  Command Line:
  </div>
  <div class="code bash"><b>$> joule --version</b>
   joule 0.1.5

   <b>$> nilmtool info</b>
   Client version: 1.10.3 Server version:
   1.10.3 <i>#... more output</i>

  </div>
  
This guide will step through the implementation of the two stage pipeline shown below:

.. image:: /images/getting_started_pipeline.png


The Reader Module
-----------------

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

Now let's add this module to our pipeline. We need to create a module
configuration file to tell Joule how to execute the module and where
to connect its output. To do this create the following file:


.. raw:: html

  <div class="header ini">
  /etc/joule/module_configs/my_reader.conf
  </div>
  <div class="code ini"><span>[Main]</span>
  <b>exec_cmd =</b> joule-random-reader
  <b>name =</b> Random Data

  <span>[Arguments]</span>
  <b>width = </b>2
  <b>rate  = </b>10
  
  <span>[Inputs]</span>
  <i># a reader has no input streams</i>

  <span>[Outputs]</span>
  <b>output =</b> /demo/random
  </div>

This connects the module to a stream called ``/demo/random``. For more
details on the configuration format see :ref:`sec-modules`. Joule
will generate an error if a module is connected to an unconfigured
stream. Configure the stream by creating the following file:


.. raw:: html

  <div class="header ini">
  /etc/joule/stream_configs/demo_reader.conf
  </div>
  <div class="code ini"><span>[Main]</span>
  <b>name =</b> Random Data
  <b>path =</b> /demo/random
  <b>datatype =</b> float32
  <b>keep =</b> 1w

  <span>[Element1]</span>
  <b>name =</b> rand1

  <span>[Element2]</span>
   <b>name =</b> rand2
  </div>

The stream configuration file specifies what kind of data the stream holds and how
long to store it in the database. For more details on the configuration format see
:ref:`sec-streams`.

Now the pipeline is ready to execute. Restart joule and check that the
new module is running:

.. raw:: html

  <div class="header bash">
  Command Line:
  </div>
  <div class="code bash"><b>$> sudo service jouled restart</b>

  <i># check status using the joule CLI</i>
  <b>$> joule modules</b>
  +-------------+---------+--------------+---------+-----+
  | Module      | Sources | Destinations | Status  | CPU |
  +-------------+---------+--------------+---------+-----+
  | Demo Reader |         | /demo/random | running | 0%  |
  +-------------+---------+--------------+---------+-----+

  <b>$> joule logs "Demo Reader"</b>
  [27 Jan 2017 18:05:41] ---starting module---
  [27 Jan 2017 18:05:41] Starting random stream: 2 elements @ 10.0Hz

  <i># confirm data is entering NilmDB</i>
  <b>$> nilmtool list -E /demo/random</b>
  /demo/random
  interval extents: Fri, 27 Jan 2017 <i># ... </i>
  total data: 1559 rows, 155.700002 seconds

  </div>

The Filter Module
-----------------

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
  <b>name =</b> Demo Filter

  <span>[Arguments]</span>
  <b>window =</b> 11
  
  <span>[Inputs]</span>
  <b>input =</b> /demo/random

  <span>[Outputs]</span>
  <b>output =</b> /demo/smoothed
  </div>

The input stream is already configured. The output will have the same
datatype and number of elements.  To configure this stream create the
following file:



.. raw:: html

  <div class="header ini">
  /etc/joule/stream_configs/my_filter.conf
  </div>
  <div class="code ini"><span>[Main]</span>
  <b>name =</b> Filtered Data
  <b>path =</b> /demo/smoothed
  <b>datatype =</b> float32
  <b>keep =</b> 1w

  <span>[Element1]</span>
  <b>name =</b> filtered1

  <span>[Element2]</span>
  <b>name =</b> filtered2
  </div>

Now the pipeline is fully configured.  Restart joule and check that
both modules are running:

.. raw:: html

  <div class="header bash">
  Command Line:
  </div>
  <div class="code bash"><b>$> sudo systemctl restart joule.service</b>

  <i># check status using joule CLI</i>
  <b>$> joule modules</b>
  +-------------+--------------+----------------+---------+-----+
  | Module      | Sources      | Destinations   | Status  | CPU |
  +-------------+--------------+----------------+---------+-----+
  | Demo Reader |              | /demo/random   | running | 0%  |
  | Demo Filter | /demo/random | /demo/smoothed | running | 0%  |
  +-------------+--------------+----------------+---------+-----+

  <b>$> joule logs "Demo Reader"</b>
  [27 Jan 2017 18:22:48] ---starting module---
  [27 Jan 2017 18:22:48] Starting random stream: 2 elements @ 10.0Hz

  <b>$> joule logs "Demo Filter"</b>
  [27 Jan 2017 18:22:48] ---starting module---
  [27 Jan 2017 18:22:48] Starting moving average filter with window size 9

  <i># confirm data is entering NilmDB</i>
  <b>$> nilmtool list -E -n /demo/*</b>
  /demo/filtered
    interval extents: Fri, 27 Jan 2017 <i># ...</i>
	    total data: 132 rows, 13.100001 seconds
  /demo/smoothed
    interval extents: Fri, 27 Jan 2017 <i># ...</i>
            total data: 147 rows, 14.600001 seconds

  </div>

Next Steps
----------

For more details on modules and streams read :ref:`using-joule` or
visit the `Lumen Documentation`_ to start visualizing your data.

.. _Lumen Documentation: /lumen/getting_started.html

