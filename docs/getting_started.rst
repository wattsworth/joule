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
		name = Random Data
		path = /demo/random 
		datatype = float32
		keep = 1w

		[Element1]
		name = rand1

		[Element2]
		name = rand2

This will allocate a new stream in NilmDB named **/demo/random** that
holds two **float32** elements. We name the first element **rand1**
and the second element **rand2**. **Note:** *If your database has an
existing stream with this name and a different layout (datatype
and/or number of elements) you must remove it before continuing.*

Next we will set up a module to write data to this stream. **joule
reader** is a multipurpose reader module provided with Joule. It can
read values from file objects, serial ports, and more. In this
demonstration we will use it to simply generate random values. When **joule
reader** is called from the command line it prints values to stdout: 

.. code-block:: bash

		$> joule reader
		#  ... list of reader modules
		$> joule reader help random
		#  ... help with the random module
		$> joule reader random 2 10
		Starting random stream: 2 elements @ 10.0Hz
		1485188853650944 0.32359053067687582 0.70028608966895545
		1485188853750944 0.72139550945715136 0.39218791387411422
		1485188853850944 0.40728044378612194 0.26446072057019654
		1485188853950944 0.61021957330250398 0.27359526775709841
		#  ... more output ...
  
Copy the following into a file at **/etc/joule/module_configs/demo_reader.conf**

.. code-block:: ini

		[Main]
		exec_cmd = joule reader random 2 10
		name = Demo Reader

		[Source]
		# a reader has no inputs
		
		[Destination]
		output = /demo/random

This will create a reader module that runs **joule reader random** and pipes
the output to **/demo/random**. That's all you need to do to set up
the capture pipeline. Restart joule and check that the new module is
running:

.. code-block:: bash

		$> sudo systemctl restart jouled

		# check status using joule commands
		$> joule modules
		+-------------+---------+--------------+---------+-----+-------------+
		| Module      | Sources | Destinations | Status  | CPU | mem         |
		+-------------+---------+--------------+---------+-----+-------------+
		| Demo Reader |         | /demo/random | running | 0%  | 33 MB (42%) |
		+-------------+---------+--------------+---------+-----+-------------+
		$> joule logs "Demo Reader"
		[27 Jan 2017 18:05:41] ---starting module---
		[27 Jan 2017 18:05:41] Starting random stream: 2 elements @ 10.0Hz

		# confirm data is entering NilmDB
		$> nilmtool list -E /demo/random
		/demo/random
		  interval extents: Fri, 27 Jan 2017 # ... 
		          total data: 1559 rows, 155.700002 seconds
			  
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
		name = Filtered Data
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

		$> joule filter
		#  ... list of filter modules
		$> joule filter help mean
		#  ... help with the mean module
		$> joule filter mean 9
		per-element moving average with a window size of 9

To add this filter to our pipeline copy the following into a file at
**/etc/joule/module_configs/demo_filter.conf**

.. code-block:: ini

		[Main]
		exec_cmd = joule filter mean 9
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

		# check status using joule commands
		$> joule modules
		+-------------+--------------+----------------+---------+-----+-------------+
		| Module      | Sources      | Destinations   | Status  | CPU | mem         |
		+-------------+--------------+----------------+---------+-----+-------------+
		| Demo Reader |              | /demo/random   | running | 0%  | 33 MB (42%) |
		| Demo Filter | /demo/random | /demo/filtered | running | 0%  | 53 MB (68%) |
		+-------------+--------------+----------------+---------+-----+-------------+
		$> joule logs "Demo Reader"
		[27 Jan 2017 18:22:48] ---starting module---
		[27 Jan 2017 18:22:48] Starting random stream: 2 elements @ 10.0Hz
		$> joule logs "Demo Filter"
		[27 Jan 2017 18:22:48] ---starting module---
		[27 Jan 2017 18:22:48] Starting moving average filter with window size 9

		# confirm data is entering NilmDB
		$> nilmtool list -E -n /demo/*
		/demo/filtered
		  interval extents: Fri, 27 Jan 2017 # ...
		          total data: 132 rows, 13.100001 seconds
		/demo/random
		  interval extents: Fri, 27 Jan 2017 # ...
	                  total data: 147 rows, 14.600001 seconds
		    
			  

