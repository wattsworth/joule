API Reference
-------------

.. note::

    The Joule Application Programming Interface (API) uses asynchronous coroutines and must be run inside an event loop.
    The examples in this documentation are from aioconsole sessions (https://aioconsole.readthedocs.io) and cannot
    be run in a standard interactive python session.

Node
++++

.. class:: joule.api.Node(url: str, loop: asyncio.AbstractEventLoop)

    Parameters:
        :url: Joule node (default: http://localhost:8088)
        :loop: Event Loop (default: current event loop)

A node represents a Joule instance and is the only means to access API methods. Joule modules have a node attribute
created automatically that can be accessed from any coroutine.

.. code-block:: python

    """ Inside a joule.ReaderModule class """
    async def run(self, parsed_args, output):
        node_info = await self.node.info()
        # other run code

Standalone scripts may create a node object manually:

    >>> import joule
    >>> my_node = joule.api.Node()

The rest of this section describes class methods separated by category.


.. _sec-node-folder-actions:

Folder Actions
''''''''''''''

.. function:: Node.folder_root() -> joule.Folder

    Retrieve the node's root folder. This returns the entire database structure as shown in the
    example below.

    Example:
        >>> root = await node.folder_root()
        >>> root
        <joule.api.Folder id=2728 name='root' description=None locked=True>
        >>> root.children
        [<joule.api.Folder id=3123 name='tmp' description=None locked=False>,
         <joule.api.Folder id=2729 name='archive' description=None locked=True>,
         <joule.api.Folder id=2730 name='live' description=None locked=True>]

.. function:: Node.folder_get(folder: Union[joule.Folder, str, int]) -> joule.Folder

    Retrieve the specified folder. Folder may be specified by a :class:`joule.api.Folder` object,
    a path, or numeric ID. Raises :exc:`joule.errors.ApiError` if folder specification is invalid.

    Examples:
        >>> folder = await node.folder_get("/parent/my_folder")  # query by path
        <joule.api.Folder id=2729 name='archive' description=None locked=True>

        >>> live = await node.folder_get(2730) # query by ID
        <joule.api.Folder id=2730 name='my_folder' description=None locked=True>

        >>> await node.folder_get("/does/not/exist") # raises ApiError
        joule.errors.ApiError: folder does not exist [404]

.. function:: Node.folder_move(source: Union[Folder, str, int], destination: Union[Folder, str, int]) -> None

    Move the *source* folder into the *destination* folder. The source and destination may be
    specified by joule.Folder objects, paths, or numeric ID's. The source folder name must be unique in the destination
    and not be locked (actively in use by a module or statically configured) Raises
    :exc:`joule.errors.ApiError` if folder specifications are invalid or the requested
    move cannot be performed. The destination is automatically created if it does not exist.

    Examples:
        >>> await node.folder_move("/parent1/my_folder","/parent2")
        >>> parent2 = await node.folder_get("/parent2")
        >>> parent2.children
        [<joule.api.Folder id=3321 name='my_folder' description=None locked=False>]

        >>> await node.folder_move("/parent1/missing_folder","/parent2") # rasises ApiError
        joule.errors.ApiError: folder does not exist [404]

.. function:: Node.folder_update(folder: joule.Folder) -> None

    Update folder attributes. The name and description are the only writable attributes.
    Raises :exc:`joule.errors.ApiError` if folder is locked or the specification is invalid

    Example:
        >>> folder = await node.folder_get("/parent/my_folder")
        <joule.api.Folder id=3329 name='my_folder' description=None locked=False>
        >>> folder.name="new name"
        >>> await node.folder_update(folder) # save the change
        >>> parent = await node.folder_get("/parent")
        >>> parent.children # folder 3329 has a new name
        [<joule.api.Folder id=3329 name='new name' description=None locked=False>]


.. function:: Node.folder_delete(folder: Union[Folder, str, int], recursive: bool) -> None:

    Delete the specified folder. If recursive is True delete any
    child folders as well. Raises :exc:`joule.errors.ApiError` if the folder specification
    is invalid or if the folder has children and recursive is False

    Example:
        >>> folder = await node.folder_get("/parent")
        >>> folder.children
        [<joule.api.Folder id=3331 name='my_folder' description=None locked=False>]
        >>> await node.folder_delete(folder, False) # raises ApiError because of child folder
        joule.errors.ApiError: specify [recursive] or remove child folders first [400]
        >>> await node.folder_delete(folder, True) # successfully removes /parent

.. _sec-node-stream-actions:

Stream Actions
''''''''''''''

.. function:: Node.stream_get(stream: Union[Stream, str, int]) -> Stream:

    Retrieve the specified stream. Stream may be specified by a :class:`joule.api.Stream` object,
    a path, or numeric ID. Raises :exc:`joule.errors.ApiError` if stream specification is invalid.

    Examples:
        >>> stream = await node.stream_get("/parent/my_folder/stream")
        <joule.api.Stream id=2627 name='stream' description='' datatype='int32'
         is_configured=False is_source=False is_destination=False locked=False decimate=True>

        >>> stream = await node.stream_get(2627)
        <joule.api.Stream id=2627 name='stream' description='' datatype='int32'
         is_configured=False is_source=False is_destination=False locked=False decimate=True>

        >>> await node.stream_get("/does/not/exist") # raises ApiError
        joule.errors.ApiError: stream does not exist [404]

.. function:: Node.stream_move(stream: Union[Stream, str, int], folder: Union[Folder, str, int]) -> None:

    Move a stream into a different folder. The stream and folder may be
    specified by objects, paths, or numeric ID's. The stream name must be unique in the destination
    and not be locked (actively in use by a module or statically configured). Raises
    :exc:`joule.errors.ApiError` if stream or folder specifications are invalid or the requested
    move cannot be performed. The destination is automatically created if it does not exist.

    Examples:
        >>> await node.stream_move("/parent1/my_folder/stream","/parent2")
        >>> parent2 = await node.folder_get("/parent2")
        >>> parent2.streams
        [<joule.api.Stream id=2627 name='stream' description='' datatype='int32'
         is_configured=False is_source=False is_destination=False locked=False decimate=True>]

        >>> await node.stream_move("/does/not/exist","/parent2") # raises ApiError
        joule.errors.ApiError: stream does not exist [404]

.. function:: Node.stream_update(stream: Stream) -> None:

    Update stream and element attributes.
    Raises :exc:`joule.errors.ApiError` if stream is locked or the specification is invalid. The datatype and
    number of elements may not be changed.

    Example:
        >>> stream = await node.stream_get("/parent/my_folder/stream")
        >>> stream.elements # Element name is "Element1"
        [<joule.api.Element id=3192 index=0, name='Element1' units=None
         plottable=True display_type='CONTINUOUS'>]
        >>> stream.elements[0].name="New Name"
        >>> await node.stream_update(stream) # send updated values to Joule
        >>> updated_stream = await node.stream_get(stream) # refresh local copy
        >>> updated_stream.elements # Element name is now "New Name"
        [<joule.api.Element id=3192 index=0, name='New Name' units=None
         plottable=True display_type='CONTINUOUS'>]

.. function:: Node.stream_delete(stream: Union[Stream, str, int]) -> None:

    Delete a stream. Stream may be specified by a :class:`joule.api.Stream` object,
    a path, or numeric ID. Raises :exc:`joule.errors.ApiError` if the stream specification
    is invalid or if the stream is locked. To remove data within a stream see :meth:`Node.data_delete`.

    Example:
        >>> folder = await node.folder_get("/parent/my_folder")
        >>> folder.streams # my_folder has one stream
        [<joule.api.Stream id=2627 name='stream' description='' datatype='int32'
         is_configured=False is_source=False is_destination=False locked=False decimate=True>]
        >>> await node.stream_delete("/parent/my_folder/stream") # delete the stream
        >>> folder = await node.folder_get("/parent/my_folder")
        >>> folder.streams # my_folder is now empty
        []


.. function:: Node.stream_create(stream: Stream, folder: Union[Folder, str, int]) -> Stream:

    Create a stream and place in the specified folder. Folder may be specified by object, path or numeric ID.
    See :class:`joule.api.Stream` for details on creating Stream objects. Raises :exc:`joule.errors.ApiError` if the
    stream or folder specification is invalid. If the folder is specified by path it will be created if it does not exist.

    Example:
        >>> new_stream = joule.api.Stream(name="New Stream")
        >>> new_stream.elements = [joule.api.Element(name="Element1")]
        >>> await node.stream_create(new_stream,"/parent/new_folder")
        <joule.api.Stream id=2628 name='New Stream' description='' datatype='float32'
         is_configured=False is_source=False is_destination=False locked=False decimate=True>



.. function:: Node.stream_info(stream: Union[Stream, str, int]) -> StreamInfo:

    Get information about a stream as a :class:`joule.api.StreamInfo` object. Stream may be specified
    by a :class:`joule.api.Stream` object, a path, or numeric ID. Raises :exc:`joule.errors.ApiError`
    if the stream specification is invalid.

    Example:
        >>> await node.stream_info("/parent/my_folder/stream")
        <joule.api.StreamInfo start=1551730769556442 end=1551751402742424
         rows=61440, total_time=20633185982>

.. _sec-node-data-actions:

Data Actions
''''''''''''

.. function:: Node.data_read(stream: Union[Stream, str, int], start: Optional[int] = None, end: Optional[int] = None, max_rows: Optional[int] = None) -> Pipe

    Read historic data from a stream. Specify timestamp bounds for a particular range or omit to read all historic data.
    This method returns a pipe which should be used to read the data. The pipe must be closed after use. See :ref:`pipes`
    for details on Joule Pipes.

    Parameters:
        :stream: Stream specification, may be a :class:`joule.api.Stream` object, path, or numeric ID
        :start: Timestamp in UNIX microseconds. Omit to read from beginning of the stream.
        :end: Timestamp in UNIX microseconds. Omit to read until the end of the stream.
        :max_rows: Return a decimated view of the data with at most this many rows, decimations are provided in powers of 4.

    Returns:
        :pipe: A :class:`joule.models.Pipe` connection to the specified stream.

    Example:
        >>> pipe = await node.data_read("/parent/my_folder/stream")
        >>> data = await pipe.read() # for large data run in a loop
        array([(1551730769556442,      0), (1551730769657062,     10),
               (1551730769757882,     20), ..., (1551751850688250, 661380),
               (1551751850795677, 661390), (1551751850896756, 661400)],
              dtype=[('timestamp', '<i8'), ('data', '<i4')])
        >>> pipe.consume(len(data)) # flush the pipe
        >>> await pipe.close() # close the data connection

.. function:: Node.data_subscribe(stream: Union[Stream, str, int]) -> Pipe

    Read live data from a stream. The stream must be actively produced by a module. This method returns a pipe which
    should be used to read the data. The pipe must be closed after use. See :ref:`pipes`
    for details on Joule Pipes.

    Example:
        >>> pipe = await node.data_read("/live/stream")
        >>> data = await pipe.read() # run in a loop for continuous updates
        array([(1551730769556442,      0), (1551730769657062,     10),
               (1551730769757882,     20), ..., (1551751850688250, 661380),
               (1551751850795677, 661390), (1551751850896756, 661400)],
              dtype=[('timestamp', '<i8'), ('data', '<i4')])
        >>> pipe.consume(len(data)) # flush the pipe
        >>> await pipe.close() # close the data connection

.. function:: Node.data_write(stream: Union[Stream, str, int], start: Optional[int] = None, end: Optional[int] = None)

    Write data to a stream. The stream must not be an active destination from any other source.
    Optionally specify start and end timestamps to remove existing data over the interval you plan to write. This is required when
    writing to a NilmDB backend as intervals are write-once. Writing into an existing interval with the default TimescaleDB
    backend will merge the new data with the existing data although this is not recommended. This method returns a pipe which
    should be used to write the data. The pipe must be closed after use. See :ref:`pipes`
    for details on Joule Pipes.

    Example:
        >>> import numpy as np
        >>> pipe_out = await node.data_write("/parent/my_folder/stream")
        >>> for i in range(4):
        ...   await pipe_out.write(np.array([[joule.utilities.time_now(), i]]))
        >>> await pipe_out.close()
        >>> pipe_in = await node.data_read("/parent/my_folder/stream") # read the data back
        >>> await pipe_in.read()
        array([(1551758297114942, 0.), (1551758297115062, 1.),
               (1551758297115090, 2.), (1551758297115111, 3.)],
              dtype=[('timestamp', '<i8'), ('data', '<f4')])

.. function:: Node.data_delete(stream: Union[Stream, str, int], start: Optional[int] = None, end: Optional[int] = None) -> None:

    Delete data from a stream. Specify timestamp bounds to delete a particular range or omit to delete all data. Deleting
    a range of data creates an interval break in the stream as show in the example below.

    Example:
        >>> await node.data_intervals("/parent/my_folder/stream")
        [[1551759387204004, 1551863787204004]]
        >>> left=1551795387204004  # Tue, 05 Mar 2019 08:16:27
        >>> right=1551831387204004 # Tue, 05 Mar 2019 19:16:27
        >>> await node.data_delete("/parent/my_folder/stream", start=left, end=right)
        >>> await node.data_intervals("/parent/my_folder/stream")
        [[1551759387204004, 1551791787204004],
         [1551831387204004, 1551863787204004]]


.. function:: Node.data_intervals(stream: Union[Stream, str, int], start: Optional[int] = None, end: Optional[int] = None) -> List

    Retrieve list of data intervals. See :ref:`sec-intervals` for details on data intervals. Specify timestamp bounds to
    list intervals over a particular range or omit to list all intervals.

    Examples:
        >>> await node.data_intervals("/parent/my_folder/stream") # unbroken data stream
        [[1551759387204004, 1551863787204004]]

        >>> await node.data_intervals("/parent/my_folder/stream") # one segment of missing data
        [[1551730769556442, 1551757125630201],
         [1551758221956119, 1551811071052711]]

        >>> await node.data_intervals("/parent/my_folder/stream") # no stream data
        []

.. _sec-node-module-actions:

Module Actions
''''''''''''''

.. function:: Node.module_list(statistics: bool = False) -> List[Module]

    Retrieve a list of the current Joule modules as :class:`joule.api.Module` objects. If statistics is True
    retrieve CPU and memory statistics for each module. Collecting statistics takes additional time
    because the CPU usage is averaged over a short time interval.

    Example:
        >>> await node.module_list()
        [<joule.api.Module id=0 name='plus1' description='adds 1 to the input' has_interface=False>,
         <joule.api.Module id=1 name='counter' description='counts up by 10s' has_interface=False>]


.. function:: Node.module_get(module: Union[Module, str, int], statistics: bool = False) -> Module

    Retrieve a specific module as a :class:`joule.api.Module` object. If statistics is True
    retrieve CPU and memory statistics for each module. Collecting statistics takes additional time
    because the CPU usage is averaged over a short time interval. Module may be specified by object,
    name, or numeric ID.

    Example:
        >>> my_module = await node.module_get("my module")
        <joule.api.Module id=0 name='my module' description='adds 1 to the input' has_interface=False>
        >>> my_module.statistics
        <joule.api.ModuleStatistics pid=1460 create_time=1551805343.4 cpu_percent=5.60 memory_percent=6.23>


.. function:: Node.module_logs(module: Union[Module, str, int]) -> List[str]

    Retrieve a list of module logs. Logs are the stdout and stderr streams from the module. The easiest way to generate
    logs is by adding print statements to a module. The maximum number of lines is controlled by the MaxLogLines parameter
    in the main configuration file (see :ref:`sec-system-configuration`). Logs are automatically rolled if a module produces
    more than the maximum number of lines. The module may be specified by object, name, or numeric ID.

    Example:
        >>> await node.module_logs("my module")
        ['[2019-03-04T22:57:01.049266]: ---starting module---',
         '[2019-03-04T22:59:02.089463]: serial input restarted',
         '[2019-03-04T23:04:36.948160]: WARNING: temperature > 98.6']


Models
++++++
.. autoclass:: joule.api.Folder
    :members:

.. autoclass:: joule.api.Stream
    :members:

.. autoclass:: joule.api.StreamInfo
    :members:

.. autoclass:: joule.api.Element
    :members:

.. autoclass:: joule.api.Module
    :members:

.. autoclass:: joule.api.ModuleStatistics
    :members:

Errors
++++++

.. autoclass:: joule.errors.SubscriptionError
.. autoclass:: joule.errors.ConfigurationError
.. autoclass:: joule.errors.ApiError


Utilities
+++++++++

.. automodule:: joule.utilities
    :members: time_now, timestamp_to_human, human_to_timestamp, yesno


