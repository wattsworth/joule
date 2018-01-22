.. _module-docs:

Module Documentation
--------------------

Joule provides module documentation at "/modules". 
The contents of this documentation is managed with the joule docs command.
The documentation engine parses specially formatted markdown emitted by modules
when they are executed with the help flag (-h). The code snippet below
shows how to implement this behaviour using the module API:

The format of  the MODULE_DOC string is explained in the sections below.

.. highlight:: python
  :linenothreshold: 5

.. code:: python

  MODULE_DOC="""
  ---
  contents of module doc
  ---
  """

  class MyModule(ReaderModule):
    def custom_args(parser):
      parser.description = MODULE_DOC
        

The documentation is sperated into key value pairs. Keys are specified
with :colons: and the value is intended below. Values may be multiple
lines.

``General Attributes``: 
  * ``name``: the module name
  * ``author``: module author
  * ``license``: software license if applicable
  * ``url``: link to the module git repository
  * ``description``: short (one line) description
  * ``usage``: how to use the module, this should include a table
      of arguments. Markdown is supported.
``Inputs``:
  Input streams. This should be the following syntax:
       name
       :  <data_type> <number of elements> other info


.. highlight:: rest
	       
.. code:: rst

   ---
   :name:
      Random Reader
   :author:
      John Donnal
   :license:
      Open
   :url:
      http://git.wattsworth.net/wattsworth/joule.git
   :description:
      generate a random data stream
   :usage:
      This is a module that generates random numbers.
      Specify width (number of elements) and the rate in Hz.
    
      | Arguments     | Description        |
      |---------------|--------------------|
      |``width``      | number of elements |
      |``rate``       | data rate in Hz    |

   :inputs:
      None
   :outputs:
      output
      :  float32 with N elements specified by [width] argument
      
   :stream_configs:
      #output#
        [Main]
	name = Random Data
	path = /path/to/output
	datatype = float32
	keep = 1w
      
	# [width] number of elements
	[Element1]
	name = Random Set 1

	[Element2]
	name = Random Set 2

	#additional elements...

   :module_config:
      [Main]
      name = Random Reader
      exec_cmd = joule modules random-reader

      [Arguments]
      width = 4
      rate = 10 #Hz

      [Outputs]
      output = /path/to/output
   ---
