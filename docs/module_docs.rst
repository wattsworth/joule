.. _module-docs:

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
