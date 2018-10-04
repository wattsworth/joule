
.. literalinclude:: /../../example_modules/jouleexamples/example_composite.py
   :language: python
   :caption: Source: ``example_modules/jouleexamples/example_composite.py``
   :linenos:

The child class must implement the :meth:`joule.CompositeModule.setup` coroutine
which should perform the following:

  1. Create modules
  2. Create local pipes for interior streams
  3. Start modules by calling :meth:`joule.BaseModule.run` with the appropriate parameters
  4. Return module tasks for execution in the main event loop

This example contains a :ref:`sec-high-bandwidth-reader` connected to a :ref:`sec-median-filter`.
The modules are connected with a :class:`joule.LocalPipe` and the output of the
filter is connected to a :class:`joule.OutputPipe` named **filtered**.

Creating Module Arguments
  In the example above, both modules receive the **parsed_args** parameter directly.
  In more complex scenarios it is often necessary to construct a :class:`argparse.Namespace` object
  for each module with the particular arguments it requires. Make sure *all* arguments are specified
  and match the expected data types The code snipped below constructs an appropriate Namespace
  object for the ArgumentParser configuration.

.. code:: python

  import json
  import argparse

  # example ArgumentParser

  args = argparse.ArgumentParser("demo")
  args.add_argument("--arg1", required=True)  # modules should use keyword arguments
  args.add_argument("--arg2", type=int, required=True)
  args.add_argument("--arg3", type=json.loads, required=True)

  # to produce these arguments manually:

  module_args = argparse.Namespace(**{
  "arg1": "a string",  # type not specified
  "arg2": 100,         # type=int
  "arg3": [100,10,4]   # type=json
  })
