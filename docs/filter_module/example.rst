.. highlight:: python


.. code-block:: python
    :caption: Source: ``example_modules/example_filter.py``
    :linenos:

    from joule import FilterModule, EmptyPipe
    from scipy.signal import medfilt
    import asyncio


    class ExampleFilter(FilterModule):
        """Apply linear scaling to input"""

        async def run(self, parsed_args, inputs, outputs):
            raw = inputs["raw"]
            scaled = outputs["scaled"]

            # linear scaling: y=mx+b
            m = 2.0
            b = 1.5

            while True:
                # read new data
                vals = await raw.read()
                # apply linear scaling y=mx+b
                vals["data"] = vals["data"] * m + b
                # write output
                await scaled.write(vals)
                # remove read data from the buffer
                raw.consume(len(vals))
                # limit execution to 1Hz chunks
                await asyncio.sleep(1)


    if __name__ == "__main__":
        r = ExampleFilter()
        r.start()


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

.. code-block:: python
    :caption: Source: ``example_modules/median_filter.py``
    :linenos:


    class MedianFilter(joule.FilterModule):
        "Compute the median of the input"

        def custom_args(self, parser):  # pragma: no cover
            parser.add_argument("window", type=int,
                                help="window length")

        async def run(self, parsed_args, inputs, outputs):
            N = parsed_args.window
            stream_in = inputs["input"]
            stream_out = outputs["output"]
            while not self.stop_requested:
                sarray_in = await stream_in.read()
                # not enough data, wait for more
                if len(sarray_in) < (N * 2):
                    # check if the pipe is closed
                    if stream_in.closed:  # pragma: no cover
                        return
                    # check if this is the end of an interval
                    # if so we can't use this data so discard it
                    if stream_in.end_of_interval:
                        stream_in.consume(len(sarray_in))
                        await stream_out.close_interval()
                    await asyncio.sleep(0.1)
                    continue
                # allocate output array
                output_len = len(sarray_in)-N+1
                sarray_out = np.zeros(output_len, dtype=stream_out.dtype)
                filtered = scipy.signal.medfilt(sarray_in['data'], [N, 1])
                bound = int(N / 2)
                sarray_out['data'] = filtered[bound:-bound]
                sarray_out['timestamp'] = sarray_in['timestamp'][bound:-bound]
                await stream_out.write(sarray_out)
                stream_in.consume(len(sarray_out))
                if stream_in.end_of_interval:
                    await stream_out.close_interval()


    if __name__ == "__main__":
        main()

The loop executes a WINDOW size median filter. Line 16 reads in new data from the “raw” stream into a
`structured array`_. Lines 19-20 execute the median filter in place. Many filtering algorithms including
median require data before and after a sample to compute the output. Modules process data in chunks
which produces artifacts at the beginning and end where there is insufficient data to compute the output.
In this instance, the first and last EDGE samples of the chunk are invalid so they are omitted from the
output in Line 23. The call to consume() on Line 26 prepends the last 2 × EDGE samples to the next input
chunk to compensate for these boundary artifacts. This execution sequence produces exactly the same
result as a median filter run over the entire dataset at once.

.. _structured array: https://docs.scipy.org/doc/numpy-1.13.0/user/basics.rec.html
