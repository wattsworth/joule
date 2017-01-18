.. _getting-started:

===============
Getting Started
===============

Before reading this section :ref:`install Joule <installing-joule>`
and make sure you are familiar with concepts of :ref:`streams
<streams>` and :ref:`modules <modules>`. Configurations shown here use
the system defaults which expect a NilmDB repository to be avaiable at
**\http://localhost/nilmdb**. If your setup is different see
:ref:`main.conf` for the full set configuration options.

A Reader Module
---------------

In this example we will create a simple data capture pipeline that
sends two random values to a stream. We will use the builtin **joule
reader** module to generate the values. See :ref:`writing_modules` for
details on building custom modules.

We start by creating a stream configuration file for the data. Copy
the following into a new file at
**/etc/joule/stream_configs/demo_random.conf**

.. code-block:: ini

		[Main]
		path = /demo/random
		datatype = float32
		keep = 1w

		[Element1]
		name = rand1

		[Element2]
		name = rand2

This will allocate a new stream at **/demo/random** that holds two
**float32** elements. We name the first element **rand1** and the
second element **rand2**. **Note:** *If your database has an existing stream
at this path with a different layout (datatype and/or number of elements)
you must remove it before continuing.*

Next we will set up a module to write data to this stream. **joule
reader** is a multipurpose reader module provided with Joule. It can
read values from file objects, serial ports, and more. In this
demonstration we will use it to simply generate random values. When **joule
reader** is called from the command line it prints values to stdout: 

.. code-block:: bash

		$> joule reader rand -h
		#  ... help text
		$> joule reader rand --width 2 --rate_ms 10
		#  ... output ...
  
Copy the following into a file at **/etc/joule/module_configs/demo_reader.conf**

.. code-block:: ini

		[Main]
		exec_cmd = joule reader rand --width 2 --rate_ms 10
		name = Demo Reader

		[Destination]
		output = /demo/random

This will create a reader module that runs **joule reader** and pipes
the output to **/demo/random**. That's all you need to do to set up
the capture pipeline. Restart joule and check that the new module is
running:

.. code-block:: bash

		$> sudo systemctl restart jouled
		$> joule modules
		+-------------+------------+---------------+---------+-----+-----+
		| Module      | Sources    | Destinations  | Status  | CPU | mem |
		+-------------+------------+---------------+---------+-----+-----+
		| Rand Reader |            | /demo/random  | running | 2%  | 1KB |
		+-------------+------------+---------------+---------+-----+-----+
		$> joule logs "Rand Reader"
		[17 Jan 2017 10:55:31] Starting random generator: 2 float32's @ 10ms


A Filter Module
---------------

In this example we will connect the reader we set up above to a filter module. We will
use the builtin **joule filter** to compute the moving average of our data.
See :ref:`writing_modules` for details on building custom modules.

Start by creating a stream configuration file for the data. Copy the
following into a new file at
**/etc/joule/stream_configs/demo_filtered.conf**

.. code-block:: ini

		[Main]
		path = /demo/filtered
		datatype = float32
		keep = 1w

		[Element1]
		name = filtered1

		[Element2]
		name = filtered2

This will allocate a new stream at **/demo/filtered** that holds two
**float32** elements. We name the first element **filtered1** and the
second element **filtered2**

Next we will set up a module that computes the moving average of **/demo/random**
and stores the output in **/demo/filtered**. **joule filter**
is a multipurpose module that can compute several different types
of filters including median, moving average, and more. When called from the command line
it will display a description of the operations it will perform on the data

.. code-block:: bash

		$> joule filter -h
		#  ... help text
		$> joule filter average --window 10
		   compute the per-element moving average using a window size of 10


To add this filter to our pipeline copy the following into a file at
**/etc/joule/module_configs/demo_filter.conf**

.. code-block:: ini

		[Main]
		exec_cmd = joule filter avaerage --window 10
		name = Demo Filter

		[Source]
		input = /demo/random
		
		[Destination]
		output = /demo/filtered

This will create a filter module that runs **joule filter** using
input from **/demo/random** and storing output in
**/demo/filtered**. Now our pipeline consists of two modules: a reader
and a filter.  Restart joule and check that both modules are running:

.. code-block:: bash

		$> sudo systemctl restart jouled
		$> joule modules
		+-------------+--------------+----------------+---------+-----+-----+
		| Module      | Sources      | Destinations   | Status  | CPU | mem |
		+-------------+--------------+----------------+---------+-----+-----+
		| Demo Reader |              | /demo/random   | running | 2%  | 1KB |
		| Demo Filter | /demo/random | /demo/filtered | running | 2%  | 1KB |
		+-------------+--------------+----------------+---------+-----+-----+
		$> joule logs "Rand Reader"
		[17 Jan 2017 10:55:31] Starting random generator: 2x float32 @ 10ms
		$> joule logs "Demo Filter"
		[17 Jan 2017 10:55:31] Starting moving average filter with window size 10


.. _main.conf:		

main.conf
---------

Joule uses a set of default configurations that should work for most
cases. These defaults can be customized by editing
**/ect/joule/main.conf** (create it if it does not exist). The example
**main.conf** below shows the full set of options and their
default settings:

.. code-block:: ini

		[NilmDB]:
		url = http://localhost/nilmdb
		InsertionPeriod = 5 # seconds

		[ProcDB]:
		DbPath = /tmp/joule-proc-db.sqlite
		MaxLogLines = 100

		[Jouled]
		ModuleDirectory = /etc/joule/module_configs
		StreamDirectory = /etc/joule/stream_configs

Start joule with the **--config** flag to use a configuration file at
an alternate location. See the list below for information on each setting.

NilmDB:URL
  address of NilmDB server
NilmDB:InsertionPeriod
  how often to send stream data to NilmDB (in seconds)
ProcDB:DbPath
  path to sqlite database used internally by joule
ProcDB:MaxLogLines
  max number of lines to keep in a module log file (automatically rolls)
Jouled:ModuleDirectory
  folder with module configuration files, each module file should in **.conf**
Jouled:StreamDirectory
  folder with stream configuration files, each stream file should end in **.conf**



