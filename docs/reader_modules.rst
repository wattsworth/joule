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

  from joule.utils import time_now
  from joule.client import ReaderModule
  import asyncio
  import numpy as np

  class ExampleReader(ReaderModule):
    "Example reader: generates random values"

    async def run(self, parsed_args, output):
      while(1):
        value = np.rand() #data from sensor
        await output.write(np.array([[time_now(), value]]))
        await asyncio.sleep(1)

  if __name__ == "__main__":
      r = ExampleReader()
      r.start()

Reader modules should extend the base ``ReaderModule`` class. The
child class must implement the ``run`` coroutine which should perform
the following in a loop:

  1. Read data from the source
  2. Timestamp data with Unix microseconds
  3. Insert data into the output stream
  4. Sleep to create the data rate

Line 11 reads data from the source (a random number function). Line 12
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
         parser.add_argument("arg", help="custom argument")
       #... other module code

   .. raw:: html

      <div class="header bash">
      Command Line:
      </div>
      <div class="code bash"><b>$> reader_demo.py -h</b>
      usage: reader_demo.py [-h] [--pipes PIPES] arg

      **module description**

      positional arguments:
        arg            custom argument
      <i>#more output...</i>
      </div>

.. method:: run(parsed_args, output)

  ``parsed_args`` is a `Namespace`_ object with the parsed command line arguments.
  Customize the argument structure by overriding :meth:`~custom_args`. ``output``
  is a :class:`JoulePipe` connected to the module's output stream.

  This coroutine should run indefinitley. See ExampleReader for typical usage.

  .. note::

    The :ref:`Example Reader` loop structure should only be used for low bandwidth
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

Local Execution
---------------

Built-in Readers
----------------

Random
''''''

File
''''



.. _ArgumentParser: https://docs.python.org/3/library/argparse.html#argparse.ArgumentParser
.. _Namespace: https://docs.python.org/3/library/argparse.html#argparse.Namespace
