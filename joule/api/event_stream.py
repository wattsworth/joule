class EventStream:
    pass


class EventStreamInfo:
    """
        API EventStreamInfo model. Received from :meth:`Node.event_stream_info` and should not be created directly.

        .. warning::
            Rows and Bytes values are approximate

        Parameters:
            start (int): timestamp in UNIX microseconds of the first data element
            end (int): timestamp in UNIX microsseconds of the last data element
            rows (int): approximate rows of data in the stream
            bytes (int): approximate size of the data on disk
            total_time (int): data duration in microseconds (start-end)

        """

    def __init__(self, start: Optional[int], end: Optional[int], rows: int,
                 total_time: int = 0, bytes: int = 0):
        self.start = start
        self.end = end
        self.rows = rows
        self.bytes = bytes
        self.total_time = total_time

    def __repr__(self):
        return "<joule.api.DataStreamInfo start=%r end=%r rows=%r, total_time=%r>" % (
            self.start, self.end, self.rows, self.total_time)

