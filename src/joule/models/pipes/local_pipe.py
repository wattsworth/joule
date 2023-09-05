import numpy as np
import asyncio
import logging
from joule.models.pipes import Pipe
from joule.models.pipes.errors import PipeError, EmptyPipe

Loop = asyncio.AbstractEventLoop
log = logging.getLogger('joule')


class LocalPipe(Pipe):
    """
           Pipe for intra-module communication.

           Args:
               layout: ``datatype_width``, for example ``float32_3`` for a three element stream
                 must. See DataStream.layout
           Keyword Args:
               name: useful for debugging with multiple pipes
               close_cb: callback coroutine executed when pipe closes
               debug: enable to log pipe usage events
    """

    def __init__(self, layout: str, name: str = None,
                 close_cb=None, debug: bool = False, stream=None, write_limit=0):

        super().__init__(name=name, layout=layout, stream=stream)
        # tunable constants
        self.TIMEOUT_INTERVAL = 0.5
        self.debug = debug

        self._interval_break = False
        self.closed = False
        self.read_buffer = np.empty((0,), dtype=self.dtype)
        self.close_cb = close_cb
        self._last_read = False  # flag to indicate pipe only has previously read data (see input_pipe.py)
        self._reread = False
        # initialize buffer and queue
        self.queue = asyncio.Queue(maxsize=write_limit)
        self.queued_rows = 0
        self.last_index = 0
        self.direction = Pipe.DIRECTION.TWOWAY
        # caching
        self._caching = False
        self._cache_index = 0
        self._cache = None

    async def read(self, flatten=False) -> np.ndarray:

        if self._failed:
            await self.close()
            raise PipeError('pipe failed')

        # if reread is set just return the old data
        if self._reread:
            self._reread = False
            if len(self.read_buffer) == 0:
                raise PipeError("No data left to reread")
            return self._format_data(self.read_buffer, flatten)

        self._interval_break = False

        # if the queue is empty and we have old data, just return the old data
        # THIS IS REMOVED, OTHERWISE THE WRITER CAN BE STARVED AND NEVER CLOSE THE PIPE
        # if self.queue.empty() and len(self.read_buffer) > 0:
        #    await asyncio.sleep(self.TIMEOUT_INTERVAL)
        #    return self._format_data(self.read_buffer, flatten)

        # otherwise wait for at least one block
        while self.queue.empty():
            # if self._last_read:
            #    raise EmptyPipe()  # trying to re-read old data
            # if the buffer is empty and the queue is empty and the pipe is closed
            if self.queue.empty() and self.closed:
                self._last_read = True  # from now on the is_empty flag will be set
                # but an error will only be generated if all the remaining data is consumed
                break  # return unconsumed data

            await asyncio.sleep(self.TIMEOUT_INTERVAL)
        data_block = self._read(flatten)

        # NOTE: There is a chance read will return an empty array-> if the producer simply closes the existing
        # interval but all of the data is already consumed. This happens typically when a module fails and has to
        # be restarted, then the inserter pipe will have no data (probably already has been read), but the terminating
        # worker adds in an interval closing block [None] to the pipe. But if the producer also closes the pipe there
        # is no reason to pass back empty data so raise an EmptyPipe exception instead

        if len(data_block) == 0 and self.closed:
            raise EmptyPipe()
        return data_block

    def read_nowait(self, flatten=False):
        """
        Same as read but this is not a coroutine. This should only be used for unit testing.

        Args:
            flatten:

        Returns:
            numpy.ndarray

        >>> data = pipe.read_nowait()
        [1, 2, 3]

        """
        if self._failed:
            raise PipeError('pipe failed')

        # if reread is set just return the old data
        if self._reread:
            self._reread = False
            if len(self.read_buffer) == 0:
                raise PipeError("No data left to reread")
            return self._format_data(self.read_buffer, flatten)

        # if the queue is empty and we have old data, just return the old data
        if self.queue.empty() and len(self.read_buffer) > 0:
            return self._format_data(self.read_buffer, flatten)

        # if the buffer is empty and the queue is empty and the pipe is closed
        if self.queue.empty() and len(self.read_buffer) == 0 and self.closed:
            raise EmptyPipe()
        # do not wait for new data, return an empty array if nothing else is available
        return self._read(flatten)

    def _read(self, flatten=False):
        # now put all the queued data together in a single array with the previous data
        # this cannot be interrupted, relies on the total size of data written to the pipe
        start = 0
        end = len(self.read_buffer)
        buffer = np.empty((self.queued_rows + end,), self.dtype)
        if self.debug:
            print("[%s:read] initialized %d row buffer" % (self.name, len(buffer)))
            print("[%s:read] adding %d rows of unconsumed data" % (self.name, len(self.read_buffer)))
        buffer[start:end] = self.read_buffer
        start = end

        while not self.queue.empty():
            block = self.queue.get_nowait()
            if block is None:
                self._interval_break = True
                break
            end = start + len(block)
            buffer[start:end] = block
            start = end
            self.queued_rows -= len(block)

        self.read_buffer = buffer[:end]
        if self.debug:
            print("[%s:read] returning %d rows" % (self.name, len(self.read_buffer)))

        return self._format_data(self.read_buffer, flatten)

    def reread_last(self):
        if len(self.read_buffer) == 0:
            raise PipeError("No data left to reread")
        self._reread = True

    @property
    def end_of_interval(self):
        return self._interval_break

    def is_empty(self):
        if self._last_read:
            return True
        if self.queue.empty() and len(self.read_buffer) == 0 and self.closed:
            return True
        return False

    def consume(self, num_rows):
        if num_rows == 0:
            return
        if num_rows < 0:
            raise PipeError("consume called with negative offset: %d" % num_rows)
        if num_rows > len(self.read_buffer):
            raise PipeError("cannot consume %d rows: only %d available"
                            % (num_rows, len(self.read_buffer)))
        if self.debug:
            print("[%s:read] consumed %d rows" % (self.name, num_rows))
        self.read_buffer = self.read_buffer[num_rows:]

    def consume_all(self):
        return self.consume(len(self.read_buffer))

    async def write(self, data: np.ndarray):
        if self._failed:
            await self.close()
            raise PipeError('pipe failed')
        if self.closed:
            raise PipeError("Cannot write to a closed pipe")
        if not self._validate_data(data):
            return
        # convert into a structured array
        sarray = self._apply_dtype(data)

        if self._caching:
            for row in sarray:
                self._cache[self._cache_index] = row
                self._cache_index += 1
                if self._cache_index >= len(self._cache):
                    await self.flush_cache()
        else:
            await self._write(sarray)

    async def _write(self, sarray):
        # send data to subscribers
        for pipe in self.subscribers:
            await pipe.write(sarray)

        # if the queue size is infinite do not wait
        if self.queue.maxsize <= 0:
            self.queue.put_nowait(sarray)
        else:
            # wait until a slot is available
            await self.queue.put(sarray)
        self.queued_rows += len(sarray)
        await asyncio.sleep(0)
        if self.debug:
            print("[%s:write] queueing block with [%d] rows" % (self.name, len(sarray)))

    def write_nowait(self, data):
        if self._failed:
            raise PipeError('pipe failed')
        if self.closed:
            raise PipeError("Cannot write to a closed pipe")
        if not self._validate_data(data):
            return

        # convert into a structured array
        sarray = self._apply_dtype(data)
        # send data to subscribers
        for pipe in self.subscribers:
            if type(pipe) is LocalPipe:
                p: LocalPipe = pipe  # to appease type checker
                p.write_nowait(sarray)
            else:
                raise PipeError("cannot write_nowait to subscriber [%s]" % pipe.name)

        self.queue.put_nowait(sarray)
        self.queued_rows += len(sarray)
        if self.debug:
            print("[%s:write] queueing block with [%d] rows" % (self.name, len(sarray)))

    def enable_cache(self, lines: int):
        self._caching = True
        self._cache = np.empty(lines, self.dtype)
        self._cache_index = 0

    async def flush_cache(self):
        if self.closed:
            raise PipeError("Cannot write to a closed pipe")
        if self._cache_index > 0:
            await self._write(self._cache[:self._cache_index])
            self._cache_index = 0
            self._cache = np.empty(len(self._cache), self.dtype)

    async def close_interval(self):
        if self._failed:
            raise PipeError('pipe failed')
        if self.closed:
            raise PipeError("Cannot write to a closed pipe")
        if self.debug:
            print("[%s:write] closing interval" % self.name)
        if self._caching:
            await self.flush_cache()
        await self.queue.put(None)
        # close intervals in any subscribers
        for pipe in self.subscribers:
            await pipe.close_interval()

    def close_interval_nowait(self):
        """
        Same as close_interval but this is not a coroutine. This should only be used for
        unit testing

        """
        if self._failed:
            raise PipeError('pipe failed')
        if self.debug:
            print("[%s:write] closing interval" % self.name)
        self.queue.put_nowait(None)
        # close intervals in any subscribers
        for pipe in self.subscribers:
            pipe.close_interval_nowait()

    def change_layout(self, layout: str):
        self._layout = layout
        self.read_buffer = np.empty((0,), dtype=self.dtype)
        self.queued_rows = 0
        self.last_index = 0
        # caching
        if self._caching:
            self._cache = np.empty(len(self._cache), self.dtype)
            self._cache_index = 0

    async def close(self):
        if self.closed:
            return
        if self._caching:
            await self.flush_cache()
        # close any subscribers
        for pipe in self.subscribers:
            await pipe.close()
        self.closed = True
        if self.close_cb is not None:
            await self.close_cb()

    def close_nowait(self):
        """
        Same as close but this is not a coroutine. This should only be used for
        unit testing

        """
        if len(self.subscribers) > 0:
            raise PipeError("cannot close_nowait subscribers, use async")
        if self.close_cb is not None:
            raise PipeError("close_cb cannot be executed, use async")
        self.closed = True
