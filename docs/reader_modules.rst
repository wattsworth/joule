Reader Modules
==============

Reader modules are designed to read data into the Joule Framework. Data can come from
sensors, system logs, HTTP API's or any other timeseries data source. Reader modules
should extend the base class ``ReaderModule`` illustrated below.

.. image:: /images/reader_module.png

The **Example Modules** repository provides templates for the basic module types as well as
unit and integration testing infrastructure. It is available
at http://git.wattsworth.net/wattsworth/example_modules.

.. raw:: html

  <div class="header bash">
  Command Line:
  </div>
  <div class="code bash"><b>$> git clone https://git.wattsworth.net/wattsworth/example_modules.git</b>
  <b>$> cd example_modules</b>
  <i># install nose2 and asynctest module to run tests</i>
  <b>$> sudo pip3 install nose2 asynctest</b>
  </div>

Example
-------

The contents of ``example_reader.py`` are shown below:

.. highlight:: python
  :linenothreshold: 5

.. code:: python

   from joule import ReaderModule, time_now
   import asyncio
   import numpy as np

   class ExampleReader(ReaderModule):
     "Example reader: generates random values"
    
     async def run(self, parsed_args, output):
        while(1):
          value = np.random.rand()  # data from sensor
          await output.write(np.array([[time_now(), value]]))
          await asyncio.sleep(1)
            
   if __name__ == "__main__":
     r = ExampleReader()
     r.start()

Reader modules should extend the base ``ReaderModule`` class. The
child class must implement the ``run`` coroutine which should perform
the following in a loop:

  1. Read data from the input
  2. Timestamp data with Unix microseconds
  3. Insert data into the output stream
  4. Sleep to create the data rate

Line 11 reads data from the input (a random number function). Line 12
timestamps the data and inserts it into the output stream. Line 13
sleeps for one second creating a 1Hz sample rate. Note that the
asyncio.sleep coroutine is used instead of the time.sleep function.

``ReaderModule`` API
--------------------

The following methods are available for the child class to override. The
``run`` method must be implemented in the child, others are optional.

.. method:: custom_args(parser)

   ``parser`` is an `ArgumentParser`_ object.  Use this method to
   add custom command line arguments to the module.

   Example:

   .. code-block:: python

     class ReaderDemo(ReaderModule):
       def custom_args(self, parser):
         parser.description = "**module description**"
	 # add optional help text to the argument
         parser.add_argument("arg", help="custom argument")
	 # parse json input
	 parser.add_argument("json_arg", type=json.loads)
	 # a yes|no argument that resolves to True|False
	 parser.add_argument("flag_arg", type=joule.yesno)
       #... other module code

   .. raw:: html

      <div class="header bash">
      Command Line:
      </div>
      <div class="code bash"><b>$> reader_demo.py -h</b>
      usage: reader_demo.py [-h] [--pipes PIPES] arg

      **module description**

      optional arguments:
        arg            custom argument
      <i>#more output...</i>
      </div>

      
   *Note*:
     Always use keyword arguments with modules so they can be specified
     in the **[Arguments]** section  of module configuration file
     
   *Tip*:
     Use the ``type`` parameter to specify a parser function. The parser
     accepts a string input and produces the associated object. 
     
.. method:: run(parsed_args, output)

  ``parsed_args`` is a `Namespace`_ object with the parsed command line arguments.
  Customize the argument structure by overriding :meth:`~custom_args`. ``output``
  is a :class:`JoulePipe` connected to the module's output stream.

  This coroutine should run indefinitley. See ExampleReader for typical usage.

  .. note::

    The loop structure in shown above in ``ExampleReader`` should only be used for low bandwidth
    data sources. Higher bandwidth data should be timestamped and written in chunks.
    This reduces the IPC overhead between modules.

  .. code-block:: python

    #process 1kHz data in 1Hz chunks
    class HighBandwidthReader(ReaderModule):
      def run(self, parsed_args, output):
        while(1):
          # read from sensor buffer
          data = np.random((1,1000))
          # use system clock for first sample
          base_ts = time_now()
          # extrapolate timestamps for other samples in chunk
          ts = np.linspace(base_ts,base_ts+1e6,1000)
          # write chunk to output stream
          await output.write(np.hstack((ts[:,None], data[:,None])))
          # create a 1Hz chunking interval
          await asyncio.sleep(1)



.. method:: stop()

   Implement custom logic for shutting down the module.

   Example:

   .. code-block:: python

     class ReaderDemo(ReaderModule):
       def stop(self):
         print("closing network sockets...")
       #... other module code



The following methods are used to interact with :class:`ReaderModule` instances

.. method:: start()

  Creates an event loop and schedules the :meth:`run` coroutine for execution. This
  method will only return if :meth:`run` exits. In most applications this
  method should be used similar to the following:

  .. code-block:: python

    class ExampleReader(ReaderModule):
      #...code for module

    if __name__ == "__main__":
      r = ExampleReader()
      r.start() #does not return

Isolated Execution
------------------

Reader modules may be executed outside of the Joule environment. When running
isolated the output stream is redirected to stdout and appears in the terminal.
This is useful for debugging problems during module development.

.. raw:: html

  <div class="header bash">
  Command Line:
  </div>
  <div class="code bash"><b>$>./demo_reader.py --args</b>
  1485188853650944 0.32359053067687582 0.70028608966895545
  1485188853750944 0.72139550945715136 0.39218791387411422
  1485188853850944 0.40728044378612194 0.26446072057019654
  1485188853950944 0.61021957330250398 0.27359526775709841
  <i># hit ctrl-c to stop </i>

  </div>

Unit Tests
----------

This section refers to **test_reader.py** in the example_modules
repository. Joule unittests are written using `asynctest
<https://asynctest.readthedocs.io/en/latest/>`_, a library built on
top of the standard **unittest** module that reduces the boilerplate of
writing tests for async coroutines.

Each unittest file should contain a single ``async.TestCase`` class. The
test runner will automatically run any functions starting with
``test_``. Each test should have a docstring explaining the input and desired output.
Tests should have three main sections as shown in the **test_reader** function below:

.. code-block:: python

		class TestReader(asynctest.TestCase):

 		    def test_reader(self):
		        " with a rate=0.1, reader should generate 10 values in 1 second "
			# 1. build test objects
			# 2. run reader in an event loop
			# 3. check the results

Build test objects
''''''''''''''''''

.. code-block:: python

		# build test objects
		my_reader = ReaderDemo()
		pipe = LocalNumpyPipe("output", layout="float32_1")
		args = argparse.Namespace(rate=0.1, pipes="unset")

1. Create an instance of the reader module. Properly designed readers
   should not require any initialization parameters.

2. Create an output pipe to receive data from the
   module. ``LocalNumpyPipe`` takes two arguments, a pipe name which
   should be a helpful string, and a layout. The layout should match
   the stream configuration file associated with your module. See the
   NumpyPipe documentation for details on local pipes and the layout
   parameter.

3. Create an args object that contains values for any custom arguments
   your module requires, it also should also initialize the pipes
   argument to "unset". In production, modules generate pipes
   automatically from their command line parameters. In testing we
   disable the pipe building routine by using the keyword "unset", and
   instead pass our own pipe to the module's run function, below.

Run event loop
''''''''''''''

.. code-block:: python

		loop = asyncio.get_event_loop()
		my_task = asyncio.ensure_future(my_reader.run(args, pipe))
		loop.call_later(1, my_task.cancel)
		try:
		    loop.run_until_complete(my_task)
		except asyncio.CancelledError:
		    pass
		loop.close()

Modules are asynchronous coroutines that run in an event loop.  The
asynctest framework provides a new event loop for each test so we can
safely use the global loop returned by ``asyncio.get_event_loop``.
This code is common boilerplate for all reader modules and in
general it should not require any customization. The code does the following:

1. Get a reference to the global event loop
2. Set up the reader to run as a ``Task`` using the arguments and pipe created earlier
3. Schedule the reader task to be cancelled after one second
4. Run the event loop ``loop`` until the reader task stops
5. When the reader task is cancelled it generates a ``CancelledError`` which can be safely ignored
6. Close the event loop so the test exits cleanly


Check results
'''''''''''''

.. code-block:: python

		result = pipe.read_nowait()
		# data should be 0,1,2,...,9
		np.testing.assert_array_equal(result['data'],
                                              np.arange(10))
		# timestamps should be about 0.1s apart
		np.testing.assert_array_almost_equal(np.diff(result['timestamp'])/1e6,
                                                     np.ones(9)*0.1, decimal=2)

This is the most important part of the test and it will vary greatly from module to module.
There are two steps:

1. Retrieve data from the pipe using ``pipe.read_nowait()``. This is
   the synchronous version of the ``read`` command and should only be
   used in testing. Modules should always use the ``await
   pipe.read()`` syntax.  By default ``read_nowait`` returns a
   structured array with a **data** field and **timestamp** field. If
   you want timestamps in column 0 and elements in columns 1-N, use
   ``read_nowait(flatten=True)``


2. Use the ``numpy.testing`` library to compare the data to an
   expected dataset you create manually.  Note that the
   ``assert_array_almost_equal`` is the preferred testing
   function. Floating point arithmetic is inexact so directly
   comparing data using ``==`` can generate spurious errors.



.. _ArgumentParser: https://docs.python.org/3/library/argparse.html#argparse.ArgumentParser
.. _Namespace: https://docs.python.org/3/library/argparse.html#argparse.Namespace
