Joule Pipes
-----------

Joule Pipes provide a protocol independent interface to data
streams. This decouples module design from pipeline
implementation. The same module can run as a remote instance, local
process, or composite coroutine without modification. The figure below
illustrates how Joule Pipes move stream data between modules.

.. image:: /images/pipe_buffer.png

Output pipes have a single method, write which transmits data through
jouled to any modules that request the stream as an input. The data
timestamps must be monotonically increasing and not overlap with any
data already sent to jouled or present in the database. Input pipes
have two methods, read and write. read returns the current contents of
the pipe buffer. The data remains in the buffer until explicitly
removed by consume. This allows modules to manage how data is chunked
simplifying streaming algorithms that require a region of samples to
compute an output value.

.. note::

  When designing modules care must be taken to ensure that they execute
  fast enough to handle streaming data. If a
  module’s memory usage increases over time this indicates the module
  cannot keep up with the input and the Joule Pipe buffers are
  accumulating data.

.. currentmodule:: joule.client

.. class:: JoulePipe

  .. method:: read(flatten=False)

    Return a numpy array of stream data. By default this is a structured
    array with "timestamp" and "data" fields. If flatten is True the array
    is an unstructured array (flat 2D matrix). This method is a coroutine.

  .. method:: write(array)

    Write array data to the stream. The array must either be structured
    with "timestamp" and "data" fields or an unstructured array with
    timestamps in column 0. Timestamps must be
    monotonically increasing and not overlap with any data already sent
    to jouled or present in the database. This method is a coroutine.

  .. method:: consume(length)

    Flush [length] data in the receive buffer. Any unflushed data will
    be prepended to the next set of data returned by :meth:`read`.




.. class:: LocalPipe(JoulePipe)

  .. method:: read_nowait(flatten=False)

    The same as :meth:`read` but executed synchronously. This is not a coroutine.

  .. method:: write_nowait(array)

    The same as :meth:`write` but executed synchronously. This is not a coroutine.


  .. method:: add_subscriber(pipe)

    Replicate stream data to [pipe]. [pipe] must be a writeable :class:`JoulePipe`
