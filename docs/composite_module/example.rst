.. code-block:: python
  :caption: Source: ``example_modules/example_composite.py``
  :linenos:

  import argparse
  from joule import CompositeModule, LocalNumpyPipe

  from high_bandwidth_reader import HighBandwidthReader
  from example_filter import ExampleFilter

  class ExampleComposite(CompositeModule):
    """ Merge reader and filter into a single module:
                [reader -> filter]->
    """
    async def setup(self, parsed_args,
                    inputs, outputs):

      #1.) create nested modules
      my_reader = HighBandwidthReader()
      my_filter = ExampleFilter()

      #2.) create local pipes for interior streams
      pipe = LocalNumpyPipe(name="raw", layout="float32_1")

      #3.) convert modules into tasks
      #  output is an interior stream (write-end)
      parsed_args = argparse.Namespace(rate=100)
      task1 = my_reader.run(parsed_args, pipe)
      #  raw is an interior stream (read-end)
      #  filtered is an exterior stream
      parsed_args = argparse.Namespace()
      task2 = my_filter.run(parsed_args,
                            {"raw": pipe},
                            {"filtered": outputs["filtered"]})

      #4.) tasks are executed in the main event loop
      return [task1, task2]

  if __name__ == "__main__":
    r = ExampleComposite()
    r.start()

Composite modules should extend the base :class:`CompositeModule` class. The
child class must implement the :meth:`joule.CompositeModule.setup` coroutine
which should perform the following:

  1. Create nested modules
  2. Create local pipes for interior streams
  3. Convert modules into tasks by calling :meth:`joule.BaseModule.run` with the appropriate parameters
  4. Return tasks for execution in the main event loop

Because this module is a composite of a :class:`joule.ReaderModule` and a
:class:`joule.FilterModule` it has no inputs and a single output. In this example the
nested modules receive parsed_args directly. In more complex scenario
it is often necessary to construct a Namespace object for each module with
the particular arguments it requires. Make sure *all* arguments are specified and match the expected data types

.. code:: python

  module_args = argparse.Namespace(**{
  "arg1": "a string",  # type not specified
  "arg2": 100,         # type=int
  "arg3": [100,10,4]   # type=json
  })
