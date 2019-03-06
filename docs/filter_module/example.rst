
.. _sec-basic-filter:

Basic Filter
^^^^^^^^^^^^

.. literalinclude:: /../../example_modules/jouleexamples/example_filter.py
   :language: python
   :caption: Source: ``example_modules/jouleexamples/example_filter.py``
   :linenos:

Filter modules should extend the base :class:`FilterModule` class. The
child class must implement the :meth:`joule.FilterModule.run` coroutine which should perform
the following in a loop:

  1. Read from input pipe(s)
  2. Perform data processing
  3. Write to output pipe(s)
  4. Consume input data

Lines 10-11 retrieve the module's :class:`joule.Pipe` connections to the
input and output streams. Line 19 reads in new data from the "raw" stream into a
Numpy `structured array`_. Line 21 applies the linear scaling to the data in place.
The data is then written to the output pipe in line 23 and the input data is removed
from the buffer on line 25. The sleep statement ensures that data is processed in large
chunks regardless of the rate at which it arrives. This ensures the system operates efficiently
by reducing the frequency of context switches and inter-process communication.

.. _sec-median-filter:

Offset Filter
^^^^^^^^^^^^^

.. literalinclude:: /../../example_modules/jouleexamples/offset_filter.py
   :language: python
   :caption: Source: ``example_modules/jouleexamples/offset_filter.py``
   :linenos:

The loop executes a WINDOW size median filter. Line 16 reads in new data from the “raw” stream into a
`structured array`_. Lines 19-20 execute the median filter in place. Many filtering algorithms including
median require data before and after a sample to compute the output. Modules process data in chunks
which produces artifacts at the beginning and end where there is insufficient data to compute the output.
In this instance, the first and last EDGE samples of the chunk are invalid so they are omitted from the
output in Line 23. The call to consume() on Line 26 prepends the last 2 × EDGE samples to the next input
chunk to compensate for these boundary artifacts. This execution sequence produces exactly the same
result as a median filter run over the entire dataset at once.

.. _structured array: https://docs.scipy.org/doc/numpy-1.13.0/user/basics.rec.html
