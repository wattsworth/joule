
.. highlight:: python

.. code-block:: python
   :caption: Source: ``example_modules/example_reader.py``
   :linenos:

   from joule import ReaderModule
   from joule.utilities import time_now
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

    from joule import ReaderModule
    from joule.utilities import time_now
    import asyncio
    import numpy as np


    class HighBandwidthReader(ReaderModule):
        #Produce 1Hz sawtooth waveform at specified sample rate

        def custom_args(self, parser):
            grp = parser.add_argument_group("module",
                                            "module specific arguments")
            grp.add_argument("--rate", type=float,
                             required=True,
                             help="sample rate in Hz")

        async def run(self, parsed_args, output):
            start_ts = time_now()
            #run 5 times per second
            period=1
            samples_per_period=np.round(parsed_args.rate*period)
            while(1):
                end_ts = start_ts+period*1e6
                ts = np.linspace(start_ts,end_ts,
                                 samples_per_period,endpoint=False)
                vals=np.linspace(0,33,samples_per_period)
                start_ts = end_ts
                chunk = np.hstack((ts[:,None], vals[:,None]))
                await output.write(chunk)
                await asyncio.sleep(period)

    if __name__ == "__main__":
        r = HighBandwidthReader()
        r.start()
