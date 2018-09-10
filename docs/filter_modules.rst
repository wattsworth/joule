Filter Modules
==============

Filter modules process data. They may have one or more input streams and one or
more output streams. Filter modules should extend the base class ``FilterModule`` illustrated below.

.. image:: /images/filter_module.png

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
	 # add optional help text to the argument
         parser.add_argument("--arg", help="custom argument")
	 # parse json input
	 parser.add_argument("--json_arg", type=json.loads)
	 # a yes|no argument that resolves to True|False
	 parser.add_argument("--flag_arg", type=joule.yesno)
       #... other module code

   .. raw:: html

      <div class="header bash">
      Command Line:
      </div>
      <div class="code bash"><b>$> filter_demo.py -h</b>
      usage: filter_demo.py [-h] [--pipes PIPES] arg

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

.. method:: run(parsed_args, inputs, outputs)

    * ``parsed_args`` -- `Namespace`_ object with the parsed command line arguments.
      Customize the argument structure by overriding :meth:`~custom_args`.
    * ``inputs`` -- Dictionary of :class:`joule.NumpyPipe` connections to
      input streams.  These should match the **[Inputs]** in the module
      configuration file (see :ref:`sec-modules` for example
      configuration file)
    * ``outputs`` -- Dictionary of :class:`joule.NumpyPipe` connections to
      output streams.  These should match the **[Outputs]** in the
      module configuration file (see :ref:`sec-modules` for example
      configuration file)

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

Isolated Execution
-------------------


.. _Git Repository: http://git.wattsworth.net/wattsworth/example_modules
.. _structured array: https://docs.scipy.org/doc/numpy-1.13.0/user/basics.rec.html
.. _ArgumentParser: https://docs.python.org/3/library/argparse.html#argparse.ArgumentParser
.. _Namespace: https://docs.python.org/3/library/argparse.html#argparse.Namespace
