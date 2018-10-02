.. _pipes:

Pipes
-----

Joule pipes provide a protocol independent interface to data
streams. This decouples module design from pipeline
implementation. There are three different pipe implementations,
:ref:`joule.LocalPipe`, :ref:`InputPipe`, and :ref:`OutputPipe` all of which derive from the common parent
:ref:`joule.Pipe`. The LocalPipe is intended for intra-module communication (see :ref:`joule.CompositeModule`).
It is bidirectional meaning it supports both read and write operations. The InputPipe and OutputPipe are unidirectional
supporting only read and write respectively. These are intended for inter-module communication with
one module's OutputPipe connected to another's InputPipe. The figure below
illustrates how pipes move stream data between modules.

.. image:: /images/pipe_buffer.png

In the figure the pipe is initially empty at Time 0. At Time 1, the producer adds four rows of data which the consumer
reads at Time 2. The consumer only consumes two rows so the last two rows of data remain
in the pipe. At Time 4 the producer writes three more rows of data which are appended to the two
unconsumed rows. The next call to read returns all five rows of data. This time the consumer consumes
all the data and the pipe is empty. Conceptually the pipe is a buffer between
the producer and consumer, however it is important to note that these are independent processes and may not even
be running on the same machine.


.. note::

  When designing modules care must be taken to ensure that they execute
  fast enough to handle streaming data. If a
  module’s memory usage increases over time this indicates the module
  cannot keep up with the input and the Joule Pipe buffers are
  accumulating data.

Intervals
+++++++++

Streams represent continuous time series data. In order to communicate the absence of data
in a stream the producer can close the current data interval. By default calls to write
are assumed to be contiguous, that is there are no missing samples in the stream. If the producer
needs to indicate that some samples are missing it should explicitly close the current interval.

.. image:: /images/intervals.png

Producer:

.. code-block:: python

    try:
        data = sensor.read()
        await pipe.write(data)
    except SensorException:
        log.error("sensor error!")
        await pipe.close_interval()

Consumer:

.. code-block:: python

    while(1):
        data = await pipe.read()
        pipe.consume(len(data))
        output = fir_filter.run(data)
        if(pipe.end_of_interval):
            fir_filter.reset()

Filters should propagate input interval breaks to the outputs

.. code-block:: python

        data = await input_pipe.read()
        input_pipe.consume(len(data))
        await output_pipe.write(data)
        if data.end_of_interval:
            await output_pipe.close_interval()

On an interval break, read will return only data within the current interval and the end_of_interval flag is set.
The next call to read clears the end_of_interval flag. Note: If the data is not consumed the next call
to read will return data from before and after the interval break. Therefore it is best practice to completely
consume data on an interval break and reset any buffers to their initial state as shown in the consumer snippet
above.


Caching
+++++++

By default a call to write will immediately send the data to the transport layer (OS pipe, network socket, etc). In
order to reduce the overhead associated with the transport layer data should be batched. Data may be batched manually
(see high_bandwidth_reader) or you may use the pipe cache to perform data batching. When the cache is enabled the transport
layer will only be executed when the specified number of rows have been written. This eliminates the performance penalty
of frequent short writes. Timestamps should be linearly interpolated for high bandwidth data rather than individually
timestamped. The cache should be sized to execute writes at about 1 Hz.

.. code-block:: python

    # sensor produces data at 1KHz
    time = time.now()
    pipe.enable_cache(1000)
    while(1):
        data_point = sensor.read()
        ts += 1000 #1ms = 1000us
        await pipe.write([[ts,data_point]])




Subscriptions
+++++++++++++

A single input can be copied to multiple outputs using pipe subscriptions. Pipes that produce output (OutputPipe or LocalPipe)
A LocalPipe can subscribe
 to input end of a LocalPipe can be
subscribed to either an OutputPipe or the output end of another LocalPipe.

.. note::

    Pipe subscriptions are only necessary for creating data paths within Composite Modules. Joule manages
    inter-module data paths automatically


.. code-block:: python

    p1.subscribe(p2)
    await p1.write([1,2,3])
    await p1.read() # 1,2,3
    p1.consume(len(data))
    # p2 still has the data
    p2.read() # 1,2,3
    p2.consume(2)
    await p1.write([4,5,6])
    p1.read() # 4,5,6
    p2.read() # 3,4,5,6

