Composite Modules
=================

Composite modules aggregate multiple modules into a single
process. They may have one or more input streams and one or
more output streams. Composite modules should extend the base
class ``CompositeModule`` illustrated below.

.. image:: /images/composite_module.png

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

Example
-------

The contents of ``example_composite.py`` are shown below:

.. highlight:: python
  :linenothreshold: 5

.. code:: python

  from joule.client import CompositeModule,
                           LocalPipe

  from example_reader import ExampleReader
  from example_filter import ExampleFilter

  class ExampleComposite(CompositeModule):
    """ Merge reader and filter into a single module:
                [reader -> filter]->
    """
    async def setup(self, parsed_args,
                    inputs, outputs):

      #1.) create nested modules
      my_reader = ExampleReader()
      my_filter = ExampleFilter()

      #2.) create local pipes for interior streams
      pipe = LocalPipe()

      #3.) convert modules into tasks
      #  *output is an interior stream (write-end)
      task1 = my_reader.run(parsed_args, pipe)
      #  *raw input is an interior stream (read-end)
      #  *filtered output is an exterior stream
      task2 = my_filter.run(parsed_args,
                            {"raw": pipe},
                            {"filtered": outputs["filtered"]})

      #4.) tasks are executed in the main event loop
      return [task1, task2]

  if __name__ == "__main__":
      r = ExampleComposite()
      r.start()

Composite modules should extend the base ``CompositeModule`` class. The
child class must implement the ``setup`` coroutine which should perform
the following:

  1. Create nested modules
  2. Create local pipes for interior streams
  3. Convert modules into tasks by calling ``run`` with the appropriate parameters
  4. Return tasks for execution in the main event loop

Because this module is a composite of a ReaderModule and a FilterModule it has no
inputs and a single output. In this example the nested modules receive parsed_args directly. In more
complex scenario you should manually construct a Namespace object for each module
with the particular arguments it requires.

``CompositeModule`` API
-----------------------

The following methods are available for the child class to override. The
``setup`` method must be implemented in the child, others are optional.

.. method:: custom_args(parser)

   ``parser`` is an `ArgumentParser`_ object.  Use this method to
   add custom command line arguments to the module.

   Example:

   .. code-block:: python

     class CompositeDemo(CompositeModule):
       def custom_args(self, parser):
         parser.description = "**module description**"
         parser.add_argument("arg", help="custom argument")
       #... other module code

   .. raw:: html

      <div class="header bash">
      Command Line:
      </div>
      <div class="code bash"><b>$> composite_demo.py -h</b>
      usage: composite_demo.py [-h] [--pipes PIPES] arg

      **module description**

      positional arguments:
        arg            custom argument
      <i>#more output...</i>
      </div>

.. method:: setup(parsed_args, inputs, outputs)

  * ``parsed_args`` -- `Namespace`_ object with the parsed command line arguments.
    Customize the argument structure by overriding :meth:`~custom_args`.
  * ``inputs`` -- Dictionary of :class:`JoulePipe` connections to input streams.
    Dictionary keys are the configuration file :ref:`input names`.
  * ``outputs`` -- Dictionary of :class:`JoulePipe` connections to output streams.
    Dictionary keys are the configuration file :ref:`output names`.
  This should return an array of coroutine objects (tasks). See ExampleComposite for typical usage.


The following methods are used to interact with :class:`CompositeModule` instances

.. method:: start()

  Creates an event loop to execute the nested modules. This
  method will only return if all the nested modules terminate.
  In most applications this method should be used similar to the following:

  .. code-block:: python

    class CompositeDemo(CompositeModule):
      #...code for module

    if __name__ == "__main__":
      r = CompositeDemo()
      r.start() #does not return


.. _Git Repository: http://git.wattsworth.net/wattsworth/example_modules
.. _structured array: https://docs.scipy.org/doc/numpy-1.13.0/user/basics.rec.html
.. _ArgumentParser: https://docs.python.org/3/library/argparse.html#argparse.ArgumentParser
.. _Namespace: https://docs.python.org/3/library/argparse.html#argparse.Namespace
