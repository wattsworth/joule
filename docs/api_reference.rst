.. _api-reference:

API Reference
-------------

.. note::

    The Joule Application Programming Interface (API) uses asynchronous coroutines and must be run inside an event loop.
    To run the examples in this documentation interactively use the asyncio module:

    .. code-block:: bash

        $> python3 -m asyncio
        asyncio REPL 3.8.10
        ...
        >>> import asyncio
        >>>

    A Jupyter Notebook that provides an overview of the API functionality is
    available `here <https://github.com/wattsworth/joule/blob/master/API_demo.ipynb>`_. To run this notebook follow
    the commands below to install `Jupyter <https://jupyter.org/>`_ and `matplotlib <https://matplotlib.org/>`_,
    retrieve the notebook file, and start the Jupyter server:

    .. code-block:: bash

        $> pip install jupyterlab matplotlib # prefix with sudo for system-wide install
        $> wget https://raw.githubusercontent.com/wattsworth/joule/master/API_demo.ipynb
        $> jupyter lab --ip=0.0.0.0 # add the --ip flag to allow external connections

Node
++++

.. class:: joule.api.Node(url: str, loop: asyncio.AbstractEventLoop)

    Parameters:
        :url: Joule node (default: http://localhost:8088)
        :loop: Event Loop (default: current event loop)

A node represents a Joule instance and is the only means to access API methods. Joule modules have a node instance
created automatically that refers to the node where it is running.

.. code-block:: python

    """ Inside a joule.ReaderModule class """
    async def run(self, parsed_args, output):
        node_info = await self.node.info()
        # other run code

Standalone scripts may connect to any authorized node using the ``api.get_node`` function:

    >>> import joule
    >>> my_node = joule.api.get_node()

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

.. _sec-node-data-stream-actions:

DataStream Actions
''''''''''''''''''

.. function:: Node.data_stream_get(stream: Union[DataStream, str, int]) -> DataStream:

    Retrieve the specified stream. DataStream may be specified by a :class:`joule.api.DataStream` object,
    a path, or numeric ID. Raises :exc:`joule.errors.ApiError` if stream specification is invalid.

    Examples:
        >>> stream = await node.data_stream_get("/parent/my_folder/stream")
        <joule.api.DataStream id=2627 name='stream' description='' datatype='int32'
         is_configured=False is_source=False is_destination=False locked=False decimate=True>

        >>> stream = await node.data_stream_get(2627)
        <joule.api.DataStream id=2627 name='stream' description='' datatype='int32'
         is_configured=False is_source=False is_destination=False locked=False decimate=True>

        >>> await node.data_stream_get("/does/not/exist") # raises ApiError
        joule.errors.ApiError: stream does not exist [404]


.. function:: Node.data_stream_move(stream: Union[DataStream, str, int], folder: Union[Folder, str, int]) -> None:

    Move a stream into a different folder. The stream and folder may be
    specified by objects, paths, or numeric ID's. The stream name must be unique in the destination
    and not be locked (actively in use by a module or statically configured). Raises
    :exc:`joule.errors.ApiError` if stream or folder specifications are invalid or the requested
    move cannot be performed. The destination is automatically created if it does not exist.

    Examples:
        >>> await node.data_stream_move("/parent1/my_folder/stream","/parent2")
        >>> parent2 = await node.folder_get("/parent2")
        >>> parent2.data_streams
        [<joule.api.DataStream id=2627 name='stream' description='' datatype='int32'
         is_configured=False is_source=False is_destination=False locked=False decimate=True>]

        >>> await node.data_stream_move("/does/not/exist","/parent2") # raises ApiError
        joule.errors.ApiError: stream does not exist [404]


.. function:: Node.data_stream_update(stream: DataStream) -> None:

    Update stream and element attributes.
    Raises :exc:`joule.errors.ApiError` if stream is locked or the specification is invalid.
    The datatype and number of elements may not be changed.

    Example:
        >>> stream = await node.data_stream_get("/parent/my_folder/stream")
        >>> stream.elements # Element name is "Element1"
        [<joule.api.Element id=3192 index=0, name='Element1' units=None
         plottable=True display_type='CONTINUOUS'>]
        >>> stream.elements[0].name="New Name"
        >>> await node.data_stream_update(stream) # send updated values to Joule
        >>> updated_stream = await node.data_stream_get(stream) # refresh local copy
        >>> updated_stream.elements # Element name is now "New Name"
        [<joule.api.Element id=3192 index=0, name='New Name' units=None
         plottable=True display_type='CONTINUOUS'>]

.. function:: Node.data_stream_delete(stream: Union[DataStream, str, int]) -> None:

    Delete a stream. DataStream may be specified by a :class:`joule.api.DataStream` object,
    a path, or numeric ID. Raises :exc:`joule.errors.ApiError` if the stream specification
    is invalid or if the stream is locked. To remove data within a stream see :meth:`Node.data_delete`.

    Example:
        >>> folder = await node.folder_get("/parent/my_folder")
        >>> folder.data_streams # my_folder has one stream
        [<joule.api.DataStream id=2627 name='stream' description='' datatype='int32'
         is_configured=False is_source=False is_destination=False locked=False decimate=True>]
        >>> await node.data_stream_delete("/parent/my_folder/stream") # delete the stream
        >>> folder = await node.folder_get("/parent/my_folder")
        >>> folder.data_streams # my_folder is now empty
        []


.. function:: Node.data_stream_create(stream: DataStream, folder: Union[Folder, str, int]) -> DataStream:

    Create a stream and place in the specified folder. Folder may be specified by object, path or numeric ID.
    See :class:`joule.api.DataStream` for details on creating DataStream objects. Raises :exc:`joule.errors.ApiError` if the
    stream or folder specification is invalid. If the folder is specified by path it will be created if it does not exist.

    Example:
        >>> new_stream = joule.api.DataStream(name="New Stream")
        >>> new_stream.elements = [joule.api.Element(name="Element1")]
        >>> await node.data_stream_create(new_stream,"/parent/new_folder")
        <joule.api.DataStream id=2628 name='New Stream' description='' datatype='float32'
         is_configured=False is_source=False is_destination=False locked=False decimate=True>

.. function:: Node.data_stream_info(stream: Union[DataStream, str, int]) -> DataStreamInfo:

    Get information about a stream as a :class:`joule.api.DataStreamInfo` object. DataStream may be specified
    by a :class:`joule.api.DataStream` object, a path, or numeric ID. Raises :exc:`joule.errors.ApiError`
    if the stream specification is invalid.

    Example:
        >>> await node.data_stream_info("/parent/my_folder/stream")
        <joule.api.DataStreamInfo start=1551730769556442 end=1551751402742424
         rows=61440, total_time=20633185982>

.. function:: Node.data_stream_annotation_delete(stream: Union[DataStream, str, int], start: Optional[int] = None,
        end: Optional[int] = None) -> None:

    Remove annotations from this stream. If start and/or end is specified only remove annotations within this range.
    If a bound is not specified it defaults to the extreme (min/max) timestamp in the stream.

.. _sec-node-data-actions:

Data Actions
''''''''''''

.. function:: Node.data_read(stream: Union[DataStream, str, int], start: Optional[int] = None, end: Optional[int] = None, max_rows: Optional[int] = None) -> Pipe

    Read historic data from a stream. Specify timestamp bounds for a particular range or omit to read all historic data.
    This method returns a pipe which should be used to read the data. The pipe must be closed after use. See :ref:`pipes`
    for details on Joule Pipes.

    Parameters:
        :stream: DataStream specification, may be a :class:`joule.api.DataStream` object, path, or numeric ID
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

.. function:: Node.data_subscribe(stream: Union[DataStream, str, int]) -> Pipe

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

.. function:: Node.data_write(stream: Union[DataStream, str, int], start: Optional[int] = None, end: Optional[int] = None)

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

.. function:: Node.data_delete(stream: Union[DataStream, str, int], start: Optional[int] = None, end: Optional[int] = None) -> None:

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


.. function:: Node.data_intervals(stream: Union[DataStream, str, int], start: Optional[int] = None, end: Optional[int] = None) -> List

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

.. _sec-node-annotation-actions:

Annotation Actions
''''''''''''''''''

.. function:: Node.annotation_create(annotation: Annotation,  stream: Union[int, str, DataStream]) -> Annotation

    Add an annotation. Create a new :class:`joule.api.Annotation` object locally and associate it with a data stream.
    The stream may be specified by path, ID, or a :class:`joule.api.DataStream` object

    Example:
        >>> from joule import utilities
        >>> event_note = Annotation(title='Event Annotation',
                               start=utilities.human_to_timestamp('now'))
        >>> await node.annotation_create(event_note, '/path/to/stream')
        >>> range_note = Annotation(title='Range Annotation',
                               start=utilities.human_to_timestamp('1 minute ago'),
                               end=utilities.human_to_timestamp('now'))
        >>> await node.annotation_create(range_note, '/path/to/stream')


.. function:: Node.annotation_delete(annotation: Union[int, Annotation]) -> None

    Remove an annotation. The annotation may be specified by ID or
    :class:`joule.api.Annotation` object.

    Example:
        >>> await node.annotation_delete(5) # assuming 5 is a valid annotation ID

.. function:: Node.annotation_update(annotation: Annotation) -> Annotation

    Update an annotation with new title or content. The time ranges (start,end) may not be changed

    Example:
        >>> await node.annotation_update(annotation) # assuming annotation already exists on the stream

.. function:: Node.annotation_get(stream: Union['DataStream', str, int], start: Optional[int], end: Optional[int]) -> List[Annotation]:

    Retrieve annotations for a particular stream. Specify timestamps to only retrieve annotations over
    a particular interval. The stream may be specified by path, ID, or a :class:`joule.api.DataStream` object

    Example:
        >>> annotations = await node.annotation_get("/path/to/stream")
        >>> print(annotations[0].name)
        "Demo Annotation"


.. _sec-node-event-stream-actions:

Event Stream Actions
''''''''''''''''''''

.. function:: Node.event_stream_get(stream: Union[EventStream, str, int]) -> EventStream

    Retrieve the specified stream. EventStream may be specified by a :class:`joule.api.EventStream` object,
    a path, or a numeric ID. Raises :exc:`joule.errors.ApiError` if stream specification is invalid.

    Examples:

        Notes

.. function:: Node.event_stream_move(stream: Union[DataStream, str, int], folder: Union[Folder, str, int]) -> None

    Move a stream into a different folder. The stream and folder may be
    specified by objects, paths, or numeric ID's. The stream name must be unique in the destination.
    Raises :exc:`joule.errors.ApiError` if stream or folder specifications are invalid or the requested
    move cannot be performed. The destination is automatically created if it does not exist.

    Examples:
        >>> await node.event_stream_move("/parent1/my_folder/stream","/parent2")
        >>> parent2 = await node.folder_get("/parent2")
        >>> parent2.event_streams
        [<joule.api.DataStream id=2627 name='stream' description='' datatype='int32'
         is_configured=False is_source=False is_destination=False locked=False decimate=True>]

        >>> await node.event_stream_move("/does/not/exist","/parent2") # raises ApiError
        joule.errors.ApiError: stream does not exist [404]

.. function:: Node.event_stream_update(stream: EventStream) -> None

    Update the event stream name and/or description. Raises :exc:`joule.errors.ApiError` if
    the specification is invalid.

    Example:
        >>> stream = await node.event_stream_get("/parent/my_folder/stream")
        >>> stream.elements # Element name is "Element1"
        [<joule.api.Element id=3192 index=0, name='Element1' units=None
         plottable=True display_type='CONTINUOUS'>]
        >>> stream.elements[0].name="New Name"
        >>> await node.data_stream_update(stream) # send updated values to Joule
        >>> updated_stream = await node.data_stream_get(stream) # refresh local copy
        >>> updated_stream.elements # Element name is now "New Name"
        [<joule.api.Element id=3192 index=0, name='New Name' units=None
         plottable=True display_type='CONTINUOUS'>]

.. function:: Node.event_stream_delete(stream: Union[EventStream, str, int]) -> None

    Delete a stream. EventStream may be specified by a :class:`joule.api.EventStream` object,
    a path, or numeric ID. Raises :exc:`joule.errors.ApiError` if the stream specification
    is invalid or if the stream is locked. To remove data within a stream see :meth:`Node.event_stream_remove`.

    Example:
        >>> folder = await node.folder_get("/parent/my_folder")
        >>> folder.event_streams # my_folder has one stream
        [<joule.api.EventStream id=39 name='stream' description='example'>
        >>> await node.event_stream_delete("/parent/my_folder/stream") # delete the stream
        >>> folder = await node.folder_get("/parent/my_folder")
        >>> folder.event_streams # my_folder is now empty
        []

.. function:: Node.event_stream_create(stream: EventStream, folder: Union[Folder, str, int]) -> EventStream

    Create an event stream and place in the specified folder. Folder may be specified by object, path or numeric ID.
    See :class:`joule.api.EventStream` for details on creating EventStream objects. Raises :exc:`joule.errors.ApiError` if the
    stream or folder specification is invalid. If the folder is specified by path it will be created if it does not exist.

    Example:
        >>> new_stream = joule.api.EventStream(name="New Stream")
        >>> await node.event_stream_create(new_stream,"/parent/new_folder")
        <joule.api.EventStream id=38 name='New Stream' description=''>

.. function:: Node.event_stream_info(stream: Union[EventStream, str, int]) -> EventStreamInfo

    Get information about a stream as a :class:`joule.api.EventStreamInfo` object. EventStream may be specified
    by a :class:`joule.api.EventStream` object, a path, or numeric ID. Raises :exc:`joule.errors.ApiError`
    if the stream specification is invalid.

    Example:
        >>> await node.event_stream_info("/parent/my_folder/stream")
        <joule.api.EventStreamInfo start=1643858892000000 end=1643891982000000
            events=10, total_time=33090000000>

.. function:: Node.event_stream_write(stream: Union[EventStream, str, int], events: List[Event]) -> None

    Add events to an existing stream. EventStream may be specified by a :class:`joule.api.EventStream` object,
    a path, or numeric ID. Events is a list of :class:`joule.api.Event` objects.

    Example:
        >>> from joule.utilities import time_now
        >>> e1 = Event(start_time=time_now()-1e6, end_time = time_now(), content={'name': 'event1'})
        >>> await asyncio.sleep(2)
        >>> e2 = Event(start_time=time_now()-1e6, end_time = time_now(), content={'name': 'event2'})
        >>> await node.event_stream_write("/plugs/events",[e1,e2])

.. function:: Node.event_stream_read(stream: Union[EventStream, str, int], start: Optional[int] = None, end: Optional[int] = None, limit: Optional[int] = None, json_filter: Optional[string]=None) -> List[Event]

    Read events from an existing stream. Returns a list of :class:`joule.api.Event` objects.

    Parameters:
        :stream: Event stream, path, numeric ID, or :class:`joule.api.EventStream` object
        :start: UNIX timestamp (microseconds). Omit to read from start of stream.
        :end: UNIX timestamp (microseconds). Omit to read to end of stream.
        :limit: Limit query to first N result.
        :json_filter: Select events based on content, see below.

    JSON Filter Format:
        Specify a list of lists where each item is a tuple of ``[key,comparison,value]``
        Outer lists are OR conditions, inner lists are AND conditions. Comparison must
        be one of the following

        * String Comparison: ``is, not, like, unlike``
        * Numeric Comparison: ``gt, gte, lt, lte, eq, neq``

    Example:
        Retrieve the first 100 events where `name` is LIKE `sample` OR `value` is between 0 AND 10:

        >>>  #       ((-------- test ----------)  OR (------test------ AND ------test-------))
        >>> filter = [[['name','like','sample']]   , [['value','gt',0],    ['value','lt',10]]]
        >>> await node.event_stream_read(stream,limit=100,json_filter=json.dumps(filter))


.. function:: Node.event_stream_remove(stream: Union[EventStream, str, int], start: Optional[int] = None, end: Optional[int] = None, json_filter: Optional[string]=None)

    Remove events from an existing stream. EventStream may be specified by a :class:`joule.api.EventStream` object,
    a path, or numeric ID. Specify start and/or end timestamps to remove over events over a specific time range. Use
    json_filter to remove events based on content.



.. _sec-node-module-actions:

Module Actions
''''''''''''''

.. function:: Node.module_list(statistics: bool = False) -> List[Module]

    Retrieve a list of the current Joule modules as :class:`joule.api.Module` objects. If statistics is True
    retrieve CPU and memory statistics for each module. Collecting statistics takes additional time
    because the CPU usage is averaged over a short time interval.

    Example:
        >>> await node.module_list()
        [<joule.api.Module id=0 name='plus1' description='adds 1 to the input' is_app=False>,
         <joule.api.Module id=1 name='counter' description='counts up by 10s' is_app=False>]


.. function:: Node.module_get(module: Union[Module, str, int], statistics: bool = False) -> Module

    Retrieve a specific module as a :class:`joule.api.Module` object. If statistics is True
    retrieve CPU and memory statistics for each module. Collecting statistics takes additional time
    because the CPU usage is averaged over a short time interval. Module may be specified by object,
    name, or numeric ID.

    Example:
        >>> my_module = await node.module_get("my module")
        <joule.api.Module id=0 name='my module' description='adds 1 to the input' is_app=False>
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


.. _sec-node-proxy-actions:

Proxy Actions
'''''''''''''

.. function:: Node.proxy_list() -> List[Proxy]

    Retrieve a list of proxied URL's as :class:`joule.api.Proxy` objects.

    Example:
        >>> await node.proxy_list()
        [<joule.api.Proxy id=0 name='flask_app' proxied_url='http://localhost:8088/interface/p0'
          target_url='http://localhost:5000'>,
         <joule.api.Proxy id=1 name='intranet_host' proxied_url='http://localhost:8088/interface/p1'
          target_url='http://internal.domain.com'>]


.. function:: Node.proxy_get(module: Union[Proxy, str, int]) -> Proxy

    Retrieve a specific proxy as a :class:`joule.api.Proxy` object. Proxy may be specified by object,
    name, or numeric ID.

    Example:
        >>> await node.proxy_get("flask app")
        <joule.api.Proxy id=0 name='flask app' proxied_url='http://localhost:8088/interface/p0'
         target_url='http://localhost:5000'>

.. _sec-node-master-actions:

Master Actions
''''''''''''''

.. function:: Node.master_add(master_type: str, identifier: str, lumen_parameters: Optional[Dict] = None) -> Master:

    Grant API access to a user or node. It is recommended to use the CLI to add masters to Joule

    Parameters:
        :master_type: one of [user|joule_node|lumen_node]
        :identifier: master name, either username, URL, or domain name
        :lumen_parameters: authentication credentials required for a lumen master

    Example:
        >>> todo


.. function:: Node.master_list() -> List[Master]

   Retrieve a list of masters that can control this node as :class:`joule.api.Master` objects.

   Example:
       >>> todo

.. function:: Node.master_removet(master: Union[Master, str])

   Remove the specified master, revokes API access priveleges

Follower Actions
''''''''''''''''


.. function:: Node.follower_list() -> List[BaseNode]

   Retrieve a list of nodes that can be controlled by this node as :class:`joule.api.BaseNode` objects.

   Example:
       >>> todo

.. function:: Node.follower_remove(follower: Union[BaseNode, str])

   Remove the specified follower, does not invalidate the associated API key

Database Actions
''''''''''''''''

.. function:: Node.db_connect() -> sqlalchemy.engine.Engine:

    Create a connection to the node database. Note the node's pg_hba.conf
    must allow remote connections to the database.

.. function:: Node.db_connection_info() -> joule.utilities.ConnectionInfo

    Connection information necessary to connect to the node database. This
    is useful if the IP address or domain name must be changed before connecting
    to the databse. Returns a :class:`joule.utilities.ConnectionInfo` object.

Models
++++++
.. autoclass:: joule.api.Folder
    :members:

.. autoclass:: joule.api.DataStream
    :members:

.. autoclass:: joule.api.DataStreamInfo
    :members:

.. autoclass:: joule.api.Element
    :members:

.. autoclass:: joule.api.Module
    :members:

.. autoclass:: joule.api.ModuleStatistics
    :members:

.. autoclass:: joule.api.Annotation
    :members:

Errors
++++++

.. autoclass:: joule.errors.ApiError
.. autoclass:: joule.errors.StreamNotFound
.. autoclass:: joule.errors.EmptyPipeError

.. note::

    The following errors are not expected in typical usage:

.. autoclass:: joule.errors.SubscriptionError
.. autoclass:: joule.errors.ConfigurationError
.. autoclass:: joule.errors.DataError
.. autoclass:: joule.errors.DecimationError


Utilities
+++++++++

.. automodule:: joule.utilities
    :members: ConnectionInfo, time_now, timestamp_to_human, human_to_timestamp, yesno


.. class:: joule.utilities.ConnectionInfo()

    Returned by :meth:`joule.api.db_connection_info`

    Parameters:
        :username (str): database username
        :password (str): database password
        :port (int): database port
        :database (str): database namne
        :host (str): hostname

    Methods:



