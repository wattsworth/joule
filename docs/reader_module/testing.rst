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
^^^^^^^^^^^^^^^^^^

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
^^^^^^^^^^^^^^

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
^^^^^^^^^^^^^

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
