.. _streams:

Streams
-------

Streams are timestamped data flows between modules. They are composed of one or more elements.
Timestamps are in Unix microseconds (elapsed time since January 1, 1970).

 ========= ======== ======== === ========
 Timestamp Element1 Element2 ... ElementN
 ========= ======== ======== === ========
 1003421   0.0      10.5     ... 2.3
 1003423   1.0      -8.0     ... 2.3
 1003429   8.0      12.5     ... 2.3
 1003485   4.0      83.5     ... 2.3
 ...       ...      ...      ... ...
 ========= ======== ======== === ========


API
+++

.. autoclass:: joule.Stream
    :members:

.. autoclass:: joule.Element
    :members:

.. automodule:: joule.errors
