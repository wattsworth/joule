
.. _sec-basic-reader:

Basic Reader
^^^^^^^^^^^^

.. literalinclude:: /../../example_modules/jouleexamples/example_reader.py
   :language: python
   :caption: Source: ``example_modules/jouleexamples/example_reader.py``
   :linenos:


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

.. _sec-high-bandwidth-reader:

High Bandwidth Reader
^^^^^^^^^^^^^^^^^^^^^

.. literalinclude:: /../../example_modules/jouleexamples/high_bandwidth_reader.py
   :language: python
   :caption: Source: ``example_modules/jouleexamples/high_bandwidth_reader.py``
   :linenos:

Describe the argument parsing setup

.. _sec-intermittent-reader:

Intermittent Reader
^^^^^^^^^^^^^^^^^^^

Another example showing how to handle sensor errors by creating intervals


.. literalinclude:: /../../example_modules/jouleexamples/intermittent_reader.py
   :language: python
   :caption: Source: ``example_modules/jouleexamples/intermittent_reader.py``
   :linenos: