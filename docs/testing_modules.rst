Testing Modules
===============

.. contents:: :local:

.. _unit_testing:

Unit Testing
------------

Unit tests run your module in isolation using mock input and output
streams.  This ensures that your module produces expected output given
a set of specified inputs. When combined with end-to-end testing, good
unit tests assure that your code will work correctly once it is
deployed. While unit tests may at first seem tedious to configure,
they greatly improve your code in two ways. First, a good test
suite prevents code regressions allowing you to refactor confidently.
Second, well written tests provide "live" documentation that others
can use to understand what your module does and how to use it.

ReaderModules
'''''''''''''

This section refers to **test_reader.py** in the example_modules
repository. Joule unittests are written using `asynctest
<https://asynctest.readthedocs.io/en/latest/>`_, a library built on
top of the standard **unittest** module that reduces the boilerplate of
writing tests for async coroutines.

Each unittest file should contain a single ``async.TestCase`` class. The
test runner will automatically run any functions starting with
``test_``. Each test should have a docstring explaining the input and desired output.
Tests should have three main sections:

1. Build test objects
2. Run reader in event loop
3. Check the resuls

.. code-block:: python

		class TestReader(asynctest.TestCase):
		
 		    def test_reader(self):
		        " with a rate=0.1, reader should generate 10 values in 1 second "
			# build test objects
			# run reader in an event loop
			# check the results

Build test objects
++++++++++++++++++

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

Run reader in an event loop
+++++++++++++++++++++++++++

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


Check the results
+++++++++++++++++

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
   
FilterModules
'''''''''''''

This section refers to **test_filter.py** in the example_modules
repository. Joule unittests are written using `asynctest
<https://asynctest.readthedocs.io/en/latest/>`_, a library built on
top of the standard **unittest** module that reduces the boilerplate of
writing tests for async coroutines.

Each unittest file should contain a single ``async.TestCase`` class. The
test runner will automatically run any functions starting with
``test_``. Each test should have a docstring explaining the input and desired output.
Tests should have three main sections:

1. Build test objects
2. Run the filter in an event loop
3. Check the resuls

.. code-block:: python

		class TestFilter(asynctest.TestCase):
		
		    def test_filter(self):
		    " with offset=2, output should be 2+input "
		    # build test objects
		    # run filter in an event loop
		    # check the results


Build test objects
++++++++++++++++++

.. code-block:: python

		my_filter = FilterDemo()
		pipe_in = LocalNumpyPipe("input", layout="float32_1")
		pipe_out = LocalNumpyPipe("output", layout="float32_1")
		args = argparse.Namespace(offset=2)
		# create the input data 0,1,2,...,9
		# fake timestamps are ok, just use an increasing sequence
		test_input = np.hstack((np.arange(10)[:, None],   # timestamp 0-9
                                        np.arange(10)[:, None]))  # data, also 0-9
		pipe_in.write_nowait(test_input)

1. Create an instance of the filter module. Properly designed filters
   should not require any initialization parameters.

2. Create the input and output pipes your module requires.
   ``LocalNumpyPipe`` takes two arguments, a pipe name which
   should be a helpful string, and a layout. The layout should match
   the stream configuration files associated with your module. See the
   NumpyPipe documentation for more details. Seed the input pipes with
   data using the ``pipe.write_nowait`` function. This is
   the synchronous version of the ``write`` command and should only be
   used in testing. Modules should always use ``await
   pipe.write``.

3. Create an args object that contains values for any custom arguments
   your module requires, it also should also initialize the pipes
   argument to "unset". In production, modules generate pipes
   automatically from the command line parameters. In testing we
   disable the pipe building routine by using the keyword "unset", and
   instead pass our in pipes directly to the module's run function, below.
		

Run the filter in an event loop
+++++++++++++++++++++++++++++++

.. code-block:: python

		loop = asyncio.get_event_loop()
		my_task = asyncio.ensure_future(
		    my_filter.run(args,
                                  {"input": pipe_in},
				  {"output": pipe_out}))
        
		loop.call_later(0.1, my_task.cancel)
		try:
		    loop.run_until_complete(my_task)
		except asyncio.CancelledError:
		    pass
		loop.close()

Modules are asynchronous coroutines that run in an event loop.  The
asynctest framework provides a new event loop for each test so we can
safely use the global loop returned by ``asyncio.get_event_loop``.
This code is common boilerplate for all reader modules and in general
it should not only require customizing the pipe dictionary used in step 2. The code
does the following:

1. Get a reference to the global event loop
2. Set up the filter to run as a ``Task`` using the arguments and pipes created earlier.
   The pipes are assembled into a dictionary and the inputs are passed first, followed by the
   outputs. The dictionary indices should match the source/destination names you expect in the module
   config file.  
3. Schedule the filter task to be cancelled after one second
4. Run the event loop ``loop`` until the filter task stops
5. When the filter task is cancelled it generates a ``CancelledError`` which can be safely ignored
6. Close the event loop so the test exits cleanly

   
Check the results
+++++++++++++++++

.. code-block:: python
		
		result = pipe_out.read_nowait()
		# data should be 2,3,4,...,11
		np.testing.assert_array_equal(result['data'],
                                              test_input[:, 1]+2)
		# timestamps should be the same as the input
		np.testing.assert_array_almost_equal(result['timestamp'],
                                                     test_input[:, 0])

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

End-to-End Testing
------------------

End-to-end (E2E) tests run your module in a mock environment that
mimics a production system.  E2E tests generally run slower than
unittests but they provide a high degree of assurance that the module
operates correctly. The e2e directory in the example_modules
repository has a complete testing infrastructure that runs your module
in a Docker container. The first time you run the test, you will
be prompted to retrieve the containers from Docker hub,
contact donnal@usna.edu for access credentials. The rest of this section
describes the structure of the e2e directory and how to run the test
framework.

.. code-block:: none
		     
		e2e
		\---bootstrap-inner.py
		    docker-compose.yml
		    main.conf
		    runner.sh
		    test.py
		    module_configs
		    \---reader.conf
		        filter.conf
		    stream_configs
		    \---raw.conf
		        filtered.conf

There are a large number of files in the test directory but you only need
to customize a few, the rest are boilerplate testing infrastructure. Run
the tests using the **runner.sh** script:

.. code-block:: bash
		   
		$> cd example_modules/e2e
		$> ./runner.sh
		#...output from Docker omitted..
		joule   | ---------[running e2e test suite]---------
		joule   | OK
		e2e_joule_1 exited with code 0
		#...output from Docker omitted...

When you run this command, you will see several lines of output from Docker as it sets up the test
environment and then tears down the environment and cleans up. The important lines of output are
shown above. These lines are produced by ``test.py`` which contains all of the testing
logic and is the only file in e2e directory which you should customize. Before writing the tests
though you need to set up the appropriate configuration files to run your module.

Configuration Files
'''''''''''''''''''

The E2E tests run joule just like a production system, therefore you
must include module and stream configuration files in order for joule
to recognize and run your module. It provides a type of "live"
documentation. These file serve as a type of "live" documentation that
others can use as a guide when setting up your module on other their
system.

The example_modules e2e test runs both the reader and filter module. The
reader module configuration is shown below:

.. code-block:: ini

		[Main]
		exec_cmd = python3 /joule-modules/reader.py 0.1
		name = Demo Reader

		[Source]

		[Destination]
		output = /demo/raw
		
The reader module has no sources and one destination called **output**
which is connected to the **/demo/raw** NilmDB stream. Note that the
exec command uses the **python3** interpreter and the module script is in
the **/joule-modules/** directory. The e2e bootstrap process copies
the contents of the project folder into **/joule-modules** on the
test container. If your module scripts are stored in subdirectories
access them at a path like
**/joule-modules/my-subdirectory/module.py**

The filter module has a similar configuration:

.. code-block:: ini

		[Main]
		exec_cmd = python3 /joule-modules/filter.py 2
		name = Demo Filter

		[Source]
		input = /demo/raw

		[Destination]
		output = /demo/filtered

It has one source, **input** which is attached to the NilmDB stream
**/demo/raw**. This stream is produced by the reader module. The
filter has one destination, **output** which is attached to the NilmDB
stream **/demo/filtered**. The **exec_cmd** has the same structure as
the reader module. Note that any arguments you added to the
``custom_args`` function in your module should be specified as command
line arguments to the **exec_cmd**.

The stream configurations for both **/demo/filtered** and **/demo/raw**
are in the **stream_configs** directory:

.. code-block:: ini

		[Main]
		name = Raw Data
		path = /demo/raw
		datatype = int32
		keep = 1w
		decimate = yes

		[Element1]
		name = counter

.. code-block:: ini

		[Main]
		name = Filtered Data
		path = /demo/filtered
		datatype = int32
		keep = 1w
		decimate = yes
		
		[Element1]
		name = filtered counter
		


test.py
'''''''

This file contains all of the testing logic. This file runs once the
joule process has started and it interrogates the system using the
same tools that would be available to an end user working on a live
installation.

.. code-block:: python

		def main():
		    time.sleep(8)   # wait for jouled to boot and get data
		    check_modules() # these functions use asserts to fail on error
		    check_data()
		    check_logs()

		def check_modules()
		    #check output from 'joule modules' command

		def check_data()
		    #check NilmDB data using 'nilmtool' commands

		def check_logs()
		    #check output from 'joule logs' command

		if __name__ == "__main__":
		    main()
		    print("OK") # no asserts failed, so things are good

Not all of these tests may be necessary for your module, they are included in the
example repository to show the range of tests that are possible rather than a prescription
of exactly which tests to perform. See the contents of **test.py** for several examples
and the e2eutils reference for details on the testing API.
