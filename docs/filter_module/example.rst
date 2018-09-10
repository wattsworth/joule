.. highlight:: python


.. code-block:: python
  :caption: Source: ``example_modules/example_filter.py``
  :linenos:

  from joule import FilterModule, EmptyPipe
  from scipy.signal import medfilt
  import asyncio

  WINDOW = 21
  EDGE = (WINDOW-1)//2

  class ExampleFilter(FilterModule):
    #Implement a WINDOW sized median filter

    async def run(self, parsed_args, inputs, outputs):
      raw = inputs["raw"]
      filtered = outputs["filtered"]
      while(1):
        #read new data
        vals= await raw.read()
        #execute median filter in place
        vals["data"] = medfilt(vals["data"],WINDOW)
        #write out valid samples
        await filtered.write(vals[EDGE:-EDGE])
        #leave unprocessed data in the pipe
        nsamples = len(vals)-2*EDGE
        if(nsamples>0):
          raw.consume(nsamples)

  if __name__ == "__main__":
    r = ExampleFilter()
    r.start()


Filter modules should extend the base :class:`FilterModule` class. The
child class must implement the :meth:`joule.FilterModule.run` coroutine which should perform
the following in a loop:

  1. Read from input pipe(s)
  2. Perform data processing
  3. Write to output pipe(s)
  4. Mark consumed input data

Lines 11-12 retrieve the module's :class:`joule.Pipe` connections to the
input and output streams. The loop executes a WINDOW size median filter.
Line 16 reads in new data from the "raw" stream into a `structured array`_. Lines
19-20 execute the median filter in place. Many filtering algorithms including
median require data before and after a sample to compute the output. Modules
process data in chunks which produces artifacts at the beginning and end where there is
insufficient data to compute the output. In this instance, the first and last
EDGE samples of the chunk are invalid so they are omitted from the output in
Line 23. The call to :meth:`joule.FilterModule.consume` on Line 26 leaves the last 2 × EDGE samples in
the input pipe to compensate for these boundary artifacts. This execution sequence
produces exactly the same result as a median filter run over the entire
dataset at once.
