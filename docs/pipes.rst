.. _pipes:

Pipes
-----

Joule pipes provide a protocol independent interface to data
streams. This decouples module design from pipeline
implementation. There are three different pipe implementations,
:class:`joule.LocalPipe`, :class:`joule.InputPipe`, and :class:`joule.OutputPipe` all of which derive
from the abstract base class
:class:`joule.Pipe`. **LocalPipe**'s are intended for intra-module communication (see :ref:`sec-composite`).
It is bidirectional meaning it supports both read and write operations. **InputPipe**'s and OutputPipe are unidirectional
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

.. _sec-intervals:

Intervals
+++++++++

Streams are divided into intervals of continuous time series data.
The first write to a pipe starts a new stream interval. Subsequent writes append
data to this interval. This indicates to data consumers that there are no missing samples
in the stream. To indicate missing data the producer closes the
interval. A new interval is started on the next write. The plot below shows a stream
with three seperate intervals indicating two regions of missing data.

.. image:: /images/intervals.png

Data Producers
    The code snippet below shows how a data producer indicates missing samples using intervals.
    In normal operation the sensor output is a single continuous stream interval. If the sensor
    has an error the exception handler closes the current interval and logs the event. See :ref:`sec-intermittent-reader`
    for a complete example.

.. code-block:: python

    while True:
        try:
            data = sensor.read()
            await pipe.write(data)
        except SensorException:
            log.error("sensor error!")
            await pipe.close_interval()

Data Consumers
    The code snippet below shows how a data consumer detects interval breaks in a stream. At an
    interval boundary read will return data up to the end of the current interval and set the end_of_interval
    flag. The next call to read will return data from the new interval and clear the flag. Any unconsumed data
    will be returned with the next read even though it is from a previous interval. Therefore it is best practice to completely
    consume data on an interval break and reset any buffers to their initial state as suggested with the fir_filter
    logic below. See :ref:`sec-median-filter` for a complete example on handling interval boundaries.

.. code-block:: python

    while True:
        data = await pipe.read()
        pipe.consume(len(data))
        output = fir_filter.run(data)
        if(pipe.end_of_interval):
            fir_filter.reset()


In general filters should propagate input interval breaks to their outputs. In other words unless
a filter can restore missing input data, it should have at least as much missing output data. The snippet below
shows the logic for propagating interval breaks.

.. code-block:: python

        data = await input_pipe.read()
        input_pipe.consume(len(data))
        await output_pipe.write(data)
        if data.end_of_interval:
            await output_pipe.close_interval()


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
A LocalPipe can subscribe to input end of a LocalPipe can be
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


Reference
+++++++++

.. autoclass:: joule.Pipe
    :members:

.. autoclass:: joule.InputPipe
    :members:

.. autoclass:: joule.OutputPipe
    :members:

.. autoclass:: joule.LocalPipe
    :members:
