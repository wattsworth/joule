.. _writing_modules:

===============
Writing Modules
===============

Modules are standalone processes managed by Joule. They are
connected to eachother and to the backing NilmDB datastore by
streams. Modules can have zero or more input streams and one or more
output streams. Joule does not impose any additional constraints on
modules but we recommend structuring modules using the reader
and filter patterns. See :ref:`joule-concepts` for more details.

The first two sections below show you how to write a custom reader or
filter by extending the **ReaderModule** and **FilterModule**
built-ins. This is recommended for most use cases. Before continuing,
clone the starter repository:

.. code-block:: bash
		
		$> git clone https://git.wattsworth.net/wattsworth/example_modules.git
		$> cd example_modules

This repository contains an example reader and filter as well as unit
testing and end to end testing infrastructure. Proper testing is
critical to designing complex modules, especially filters.

Extending ReaderModule
----------------------

This section explains how to use the **ReaderModule** class to develop
a custom reader module. The code snippets in this section refer to the
**ReaderDemo** module defined in **reader.py** from the example_modules
repository.

A reader module should extend from the base class **ReaderModule**, and
provide custom functionality by overriding the parent methods:

.. code-block:: python

		from joule.client import ReaderModule

		class ReaderDemo(ReaderModule):
		"Example reader: generates incrementing values at user specified rate"
  		    #...your code here...

The module should provide a custom ``__init__`` function which calls
the parent, and may define two special properties: **description** and
**help**. The description property should be a short one line summary of the module
eg "reads data from serial port", and the help property should be a longer, multiline
string explaining what the module does and how to use it, preferably with a usage example.
These properties are used by the **joule reader** help system.
You may also add any additional initialization code your module requires.

.. code-block:: python
		
		def __init__(self):
   		    super(ReaderDemo, self).__init__("Demo Reader")
		    self.description = "one line: demo reader"
		    self.help = "a paragraph: this reader does x,y,z etc..."
		    #...your custom initialization...

The module must also provide an implementation of
``custom_args``. This function receives a parser object and may add
custom arguments to it. See the `argparse documentation
<https://docs.python.org/3/library/argparse.html>`_ for details on
adding arguments to the parser.  These arguments will be available to
the ``run`` function.

.. code-block:: python

		def custom_args(self, parser):
		    parser.add_argument("rate", type=float, help="period in seconds")
		    #...additional arguments as required...
		    
		# ... or, if your module does not require arguments
		def custom_args(self, parser):
		    pass

Finally, the module must implement ``run``. This function performs the
actual work in the module.  It is an asynchronous coroutine but you
can treat it as a normal function. See the `asyncio documenation
<https://docs.python.org/3/library/asyncio.html>`_ for details on
coroutines.

.. code-block:: python

		async def run(self, parsed_args, output): #<-- this is a coroutine
		    count = 0
		    while(1):
  		       await output.write(np.array([[time_now(), count]])) #<--note await syntax
		       await asyncio.sleep(parsed_args.rate) #can also use time.sleep()
		       count += 1

This function takes two parameters, **parsed_args** and
**output**. The parsed_args is a namespace object with values for the
arguments specified in **custom_args**. **output** is a NumpyPipe that connects the module
to the joule system. The pipe has a single function, **write** which accepts a numpy array.
The array should be a matrix of timestamps and values, if you are inserting a single sample,
enclose the matrix in double braces to provide the correct dimension. Also note that the
**write** method is a coroutine and must be called with the **await** keyword.

.. code-block:: python

   data = np.array([[ts, val, val, val, ...],
                    [ts, val, val, val, ...],
          	    ....])

   await output.write(data)
   
If you run the filter from the command line it will print values to stdout. This can help
debug your code. Additionally it is best practice to provide unittests for your custom reader
modules. See **test_reader.py** for an example.


Extending FilterModule
----------------------
This section explains how to use the **FilterModule** class to develop
a custom filter module. The code snippets in this section refer to the
**FilterDemo** module defined in **filter.py** from the example_modules
repository.

A filter module should extend from the base class **FilterModule**, and
provide custom functionality by overriding the parent methods:

.. code-block:: python

		from joule.client import FilterModule

		class FilterDemo(FilterModule):
		" Example filter: applies a dc offset "
		    #...your code here...
		
The module should provide a custom ``__init__`` function which calls
the parent, and may define two special properties: **description** and
**help**. The description property should be a short one line summary of the module
eg "computes a moving average", and the help property should be a longer, multiline
string explaining what the module does and how to use it, preferably with a usage example.
These properties are used by the **joule filter** help system.
You may also add any additional initialization code your module requires.

.. code-block:: python
		
		def __init__(self):
   		    super(ReaderDemo, self).__init__("Demo Reader")
		    self.description = "one line: demo reader"
		    self.help = "a paragraph: this reader does x,y,z etc..."
		    #...your custom initialization...

The module must also provide an implementation of
``custom_args``. This function receives a parser object and may add
custom arguments to it. See the `argparse documentation
<https://docs.python.org/3/library/argparse.html>`_ for details on
adding arguments to the parser.  These arguments will be available to
the ``run`` function.

.. code-block:: python

		def custom_args(self, parser):
   		    parser.add_argument("offset", type=float, default=0,
                            help="apply an offset")
		    #...additional arguments as required...
		    
		# ... or, if your module does not require arguments
		def custom_args(self, parser):
		    pass

Finally, the module must implement ``run``. This function performs the
actual work in the module.  It is an asynchronous coroutine but for the most part you
can treat it as a normal function. See the `asyncio documenation
<https://docs.python.org/3/library/asyncio.html>`_ for details on
coroutines.

.. code-block:: python

		async def run(self, parsed_args, inputs, outputs): #<-- this is a coroutine
		    stream_in = inputs["input"]    #<--access pipes by name
		    stream_out = outputs["output"]
		    while(1):
			sarray = await stream_in.read()     #<--note await syntax
			sarray["data"] += parsed_args.offset
			await stream_out.write(sarray)      #<--note await syntax
			stream_in.consume(len(sarray))      #<--indicates

This function takes three parameters, **parsed_args**, **inputs**, and
**outputs**. The parsed_args is a namespace object with values for the
arguments specified in **custom_args**. **inputs** and **outputs** are
dictionaries of NumpyPipes indexed the names specified in the module
configuration file. These pipes connect the module to the joule system.

.. code-block:: ini

		[Main]
		exec_cmd = python3 filter.py 
		name = Demo Filter
		
		[Source]
		input = /demo/raw #<--name used in inputs dictionary
		
		[Destination]
		output = /demo/filtered #<--name used in outputs dictionary


The input pipes have two functions, **read** and **consume**. Access
data in the pipe using the read function which is a coroutine. This
returns a structured Numpy array by default, if you would like a
flattened array, set the optional parameter flatten.

.. code-block:: python

		values = await stream_in.read()
		# returns a structured array
		# values['timestamp'] = [ts, ts, ts, ..., ts]
		# values['data'] = [[val1, val2, val3, ..., valN],
		#                   [val1, val2, val3, ..., valN],...]

		values = await stream_in.read(flatten=True)
		# returns a flat array
		# values = [[ts, val1, val2, val3, ..., valN],
		            [ts, val1, val2, val3, ..., valN],...]
			    
Every call to **read** should followed by **consume** to indicate how
much of the data your module has used. The next call to **read** will
prepend any unconsumed data from the previous read. This allows you to
design filters which operate on only a portion of the input data such
as linear filters. See the built-in **mean** and **median** filters
for an example of using a portion of the input data.

The **ouput** pipes have a single function **write** which accepts
a Numpy array. See the ReaderModule section for more details on output pipes.

Unlike ReaderModules, modules derived from FilterModule cannot be run
from the command line because filters require an input stream provided
by the joule environment.You should always verify your modules using
unittests. The testing framework provides mock input streams to test
modules in isolation, see **test_filter.py** for an example.

Custom Modules
--------------
writing modules from scratch


Advanced Modules
----------------
using local numpy pipes
