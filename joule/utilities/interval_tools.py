import heapq


# Adapted from Jim Paris

def interval_difference(src, dest):
    """Helper for set_difference, intersection functions,
    to compute interval subsets based on a math operator on ranges
    present in A and B.  Subsets are computed from A, or new intervals
    are generated if subset = False."""

    result = []

    # Iterate through all starts and ends in sorted order.  Add a
    # tag to the iterator so that we can figure out which one they
    # were, after sorting.
    def decorate(intervals, key_start, key_end):
        for interval in intervals:
            yield interval[0], key_start, interval
            yield interval[1], key_end, interval

    src_iter = decorate(iter(src), 0, 2)
    dest_iter = decorate(iter(dest), 1, 3)

    # Now iterate over the timestamps of each start and end.
    # At each point, evaluate which type of end it is, to determine
    # how to build up the output intervals.
    in_src = False
    in_dest = False
    out_start = None
    for (ts, k, i) in imerge(src_iter, dest_iter):
        if k == 0:
            in_src = True
        elif k == 1:
            in_dest = True
        elif k == 2:
            in_src = False
        elif k == 3:
            in_dest = False
        include = in_src and not in_dest
        if include and out_start is None:
            out_start = ts
        elif not include:
            if out_start is not None and out_start != ts:
                result.append([out_start, ts])
            out_start = None

    return result

# Iterator merging, based on http://code.activestate.com/recipes/491285/
def imerge(*iterables):
    """Merge multiple sorted inputs into a single sorted output.

    Equivalent to:  sorted(itertools.chain(*iterables))

    >>> list(imerge([1,3,5,7], [0,2,4,8], [5,10,15,20], [], [25]))
    [0, 1, 2, 3, 4, 5, 5, 7, 8, 10, 15, 20, 25]

    """
    heappop, siftup, _Stop = heapq.heappop, heapq._siftup, StopIteration

    h = []
    h_append = h.append
    for it in map(iter, iterables):
        try:
            next = it.__next__
            h_append([next(), next])
        except _Stop:
            pass
    heapq.heapify(h)

    while 1:
        try:
            while 1:
                v, next = s = h[0]      # raises IndexError when h is empty
                yield v
                s[0] = next()           # raises StopIteration when exhausted
                siftup(h, 0)            # restore heap condition
        except _Stop:
            heappop(h)                  # remove empty iterator
        except IndexError:
            return
