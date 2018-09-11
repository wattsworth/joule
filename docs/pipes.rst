.. _pipes:

Pipes
-----

Joule pipes provide a protocol independent interface to data
streams. This decouples module design from pipeline
implementation. There are three different pipe implementations,
LocalPipe, InputPipe, and OutputPipe.
The LocalPipe is intended for intra-module communication (see CompositeModule).
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

Caching
+++++++

Subscribers
+++++++++++

