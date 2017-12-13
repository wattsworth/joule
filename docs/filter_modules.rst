Filter Modules
==============

Filter modules process data. They may have one or more input streams and one or
more output streams. Filter modules should extend the base class ``FilterModule`` illustrated below.

.. image:: /images/filter_module.png

The **Example Modules** repository provides templates for the basic module types as well as
unit and integration testing infrastructure. It is available
on the Wattsworth `Git Repository`_

.. raw:: html

  <div class="header bash">
  Command Line:
  </div>
  <div class="code bash"><b>$> git clone https://git.wattsworth.net/wattsworth/example_modules.git</b>
  <b>$> cd example_modules</b>
  <i># install nose2 and asynctest module to run tests</i>
  <b>$> sudo pip3 install nose2 asynctest</b>
  </div>

Example Filter
--------------
The contents of ``example_filter.py`` are shown below:

.. highlight:: python
  :linenothreshold: 5

.. code:: python

  from joule.client import FilterModule
  from scipy.signal import medfilt
  WINDOW = 21
  EDGE = (WINDOW-1)/2

  class ExampleFilter(FilterModule):
    #Implement a WINDOW sized median filter

    async def run(self, parsed_args, inputs, outputs):
      #retrieve JoulePipes
      raw = inputs["raw"]
      filtered = outputs["filtered"]

      while(1):
        #read new data
        vals= await raw.read()

        #execute median filter in place
        data = raw["data"]
        data = np.medfilt(data,WINDOW)

        #write out valid samples
        await filtered.write(vals[EDGE:-EDGE,:])

        #prepend trailing samples to next read
        raw.consume(len(vals)-2*EDGE)

  if __name__ == "__main__":
    r = MedianFilter()
    r.start()

Filter modules should extend the base ``FilterModule`` class. The
child class must implement the ``run`` coroutine which should perform
the following in a loop:

  1. Read from input pipe(s)
  2. Perform data processing
  3. Write to output pipe(s)
  4. Mark consumed input data

Lines 11-12 retrieve the module's :class:`JoulePipe` connections to the
input and output streams. The loop executes a WINDOW size median filter.
Line 16 reads in new data from the "raw" stream into a `structured array`_. Lines
19-20 execute the median filter in place. Many filtering algorithms including
median require data before and after a sample to compute the output. Modules
process data in chunks which produces artifacts at the beginning and end where there is
insufficient data to compute the output. In this instance, the first and last
EDGE samples of the chunk are invalid so they are omitted from the output in
Line 23. The call to :meth:`consume` on Line 26 prepends the last 2 × EDGE samples to
the next input chunk to compensate for these boundary artifacts. This execution sequence
produces exactly the same result as a median filter run over the entire
dataset at once.

``FilterModule`` API
--------------------

The following methods are available for the child class to override. The
``run`` method must be implemented in the child, others are optional.

.. method:: custom_args(parser)

   ``parser`` is an `ArgumentParser`_ object.  Use this method to
   add custom command line arguments to the module.

   Example:

   .. code-block:: python

     class FilterDemo(FilterModule):
       def custom_args(self, parser):
         parser.description = "**module description**"
         parser.add_argument("arg", help="custom argument")
       #... other module code

   .. raw:: html

      <div class="header bash">
      Command Line:
      </div>
      <div class="code bash"><b>$> filter_demo.py -h</b>
      usage: filter_demo.py [-h] [--pipes PIPES] arg

      **module description**

      positional arguments:
        arg            custom argument
      <i>#more output...</i>
      </div>

.. method:: run(parsed_args, inputs, outputs)

    * ``parsed_args`` -- `Namespace`_ object with the parsed command line arguments.
      Customize the argument structure by overriding :meth:`~custom_args`.
    * ``inputs`` -- Dictionary of :class:`JoulePipe` connections to input streams.
      Dictionary keys are the configuration file :ref:`input names`.
    * ``outputs`` -- Dictionary of :class:`JoulePipe` connections to output streams.
      Dictionary keys are the configuration file :ref:`output names`.
  This coroutine should run indefinitley. See ExampleFilter for typical usage.

.. method:: stop()

   Implement custom logic for shutting down the module.

   Example:

   .. code-block:: python

     class FilterDemo(FilterModule):
       def stop(self):
         print("closing open files...")
       #... other module code



The following methods are used to interact with :class:`FilterModule` instances

.. method:: start()

  Creates an event loop and schedules the :meth:`run` coroutine for execution. This
  method will only return if :meth:`run` exits. In most applications this
  method should be used similar to the following:

  .. code-block:: python

    class ExampleFilter(FilterModule):
      #...code for module

    if __name__ == "__main__":
      r = ExampleFilter()
      r.start() #does not return

Unit Testing
------------

TODO

Integration Testing
-------------------

TODO

.. _Git Repository: http://git.wattsworth.net/wattsworth/example_modules
.. _structured array: https://docs.scipy.org/doc/numpy-1.13.0/user/basics.rec.html
.. _ArgumentParser: https://docs.python.org/3/library/argparse.html#argparse.ArgumentParser
.. _Namespace: https://docs.python.org/3/library/argparse.html#argparse.Namespace
