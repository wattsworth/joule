
.. highlight:: python

.. code-block:: python
   :caption: Source: ``example_modules/example_reader.py``
   :linenos:

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

Reader modules should extend the base :class:`joule.ReaderModule` class. The
child class must implement the :meth:`joule.ReaderModule.run` coroutine which should perform
the following in a loop:

  1. Read data from the input
  2. Timestamp data with Unix microseconds
  3. Insert data into the output stream
  4. Sleep to create the data rate

Line 11 reads data from the input (a random number function). Line 12
timestamps the data and inserts it into the output stream. Line 13
sleeps for one second creating a 1Hz sample rate. Note that the
asyncio.sleep coroutine is used instead of the time.sleep function.


  .. note::

    The loop structure shown above should only be used for low bandwidth
    data sources. For higher bandwidth data pipe caching should be enabled or
    the data should be written in chunks as shown below. Write frequency should be 1Hz
    or lower to reduce inter-process communication and network overhead.

  .. code-block:: python
    :caption: Source: ``example_modules/high_bandwidth_reader.py``
    :linenos:

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
