Reader Modules
==============



``ReaderModule`` API
--------------------

The following methods are available for the child class to override. The
``run`` method must be implemented in the child, others are optional.

.. method:: custom_args(parser)


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


Built-in Readers
----------------

Random
''''''
TODO

File
''''
TODO

