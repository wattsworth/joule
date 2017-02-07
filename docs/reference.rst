Reference
===============

.. contents:: :local:
	      
Command Line Utilities
----------------------

joule
'''''

jouled
''''''

nilmtool
''''''''


Configuration Files
-------------------



	      
.. _main.conf:		

main.conf
'''''''''

Joule uses a set of default configurations that should work for most
cases. These defaults can be customized by editing
**/etc/joule/main.conf**. Start joule with the **--config** flag to use a configuration file at
an alternate location. The example **main.conf** below shows the
full set of options and their default settings:

.. code-block:: ini

		[NilmDB]
		url = http://localhost/nilmdb
		InsertionPeriod = 5 

		[ProcDB]
		DbPath = /tmp/joule-proc-db.sqlite
		MaxLogLines = 100

		[Jouled]
		ModuleDirectory = /etc/joule/module_configs
		StreamDirectory = /etc/joule/stream_configs

See the list below for information on each setting.

``NilmDB``
  * ``url``: address of NilmDB server
  * ``InsertionPeriod``: how often to send stream data to NilmDB (in seconds)
``ProcDB``
  * ``DbPath``: path to sqlite database used internally by joule
  * ``MaxLogLines``: max number of lines to keep in a module log file (automatically rolls)
``Jouled``
  * ``ModuleDirectory``: folder with module configuration files (absolute path)
  * ``StreamDirectory``: folder with stream configuration files (absolute path)

  
stream configs
''''''''''''''

.. code-block:: ini
		
		[Main]
		#required settings (examples)
		path = /nilmdb/path/name
		datatype = float32
		keep = 1w
		#optional settings (defaults)
		decimate = yes

		[Element1...ElementN]
		#required settings (examples)
		name         = Element Name
		#optional settings (defaults)
		plottable    = yes
		discrete     = no
		offset       = 0.0
		scale_factor = 1.0
		default_max  = null
		default_min  = null

module configs
''''''''''''''

.. code-block:: ini

		[Main]
		#required
		name = module name
		exec_cmd = /path/to/executable --args 
		#optional
		description = a short description
		
		[Source]
		path1 = /nilmdb/input/stream1
		path2 = /nilmdb/input/stream2
		# additional sources...

		[Destination]
		path1 = /nilmdb/output/stream1
		path2 = /nilmdb/output/stream2
		# additional destinations...
		
.. _numpy_pipes:

Numpy Pipes
-----------

Concepts
''''''''

Methods
'''''''

E2E Utilities
-------------

joule
'''''

nilmtool
''''''''



