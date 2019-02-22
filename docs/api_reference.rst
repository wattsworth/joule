API Reference
-------------

Node
++++

Stuff about the Node class

Folder Actions
''''''''''''''

.. function:: Node.folder_root() -> joule.Folder

    Retrieve the node's root folder.

    Example:
        >>> root = await node.folder_root()
        >>> root.parent == None # this is the root

.. function:: Node.folder_get(folder: Union[joule.Folder, str, int]) -> joule.Folder

    Retrieve the specified folder. Folder may be specified by a Folder object,
    a path, or numeric ID. Raises errors.ApiError if folder specification is invalid.

    Example:
        >>> datasets = node.folder_get("/example/datasets")
        >>> other_folder = node.folder_get(25)

.. function:: Node.folder_move(source: Union[Folder, str, int], destination: Union[Folder, str, int]) -> None

    Move the *source* folder into the *destination* folder. The source and destination may be
    specified by joule.Folder objects, paths, or numeric ID's. Raises
    errors.ApiError if folder specifications are invalid or the requested
    move cannot be performed.

    Example:
        >>> folder1 = await node.folder_get("/folder1")
        >>> await node.folder_move(folder1,"/parent")
        >>> parent = await node.folder_get("/parent")
        >>> parent.children
        >>> [folder1]

.. function:: Node.folder_update(folder: joule.Folder) -> None

    Update writable attributes for the folder. The name and
    description are the only writable attributes for the Folder model.

    Example:
        >>> folder = await node.folder_get("/folder")
        >>> folder.description = "new description"
        >>> await node.folder_update(folder)
        >>> refreshed_folder = await node.folder_get(folder)
        >>> refreshed_folder.description
        >>> the description


.. function:: Node.folder_delete(folder: Union[Folder, str, int], recursive: bool) -> None:

    Delete the specified folder. If recursive is True delete any
    child folders as well. Raises errors.apiError if the folder specification
    is invalid or if the folder has children and recursive is False

    Example:
        >>> folder = await node.folder_get("/parent")
        >>> await node.folder_delete(folder, False)
        >>> # raises error
        >>> await node.folder_delete(folder, True)
        >>> # all children folders are removed

Stream Actions
''''''''''''''

stream_get
``````````

.. autofunction:: joule.api.Node.stream_get

stream_move
```````````

.. autofunction:: joule.api.Node.stream_move


stream_update
`````````````

.. autofunction:: joule.api.Node.stream_update

stream_delete
`````````````

.. autofunction:: joule.api.Node.stream_delete


stream_create
`````````````

.. autofunction:: joule.api.Node.stream_create

stream_info
```````````

.. autofunction:: joule.api.Node.stream_info

Data Actions
''''''''''''

data_read
`````````

.. autofunction:: joule.api.Node.data_read


data_write
``````````

.. autofunction:: joule.api.Node.data_write

data_delete
```````````

.. autofunction:: joule.api.Node.data_delete

Module Actions
''''''''''''''

module_list
```````````
.. autofunction:: joule.api.Node.module_list

module_get
``````````

.. autofunction:: joule.api.Node.module_get

module_logs
```````````
.. autofunction:: joule.api.Node.module_logs

Folder
++++++
.. autoclass:: joule.api.Folder
    :members:

Stream
++++++

.. autoclass:: joule.api.Stream
    :members:

StreamInfo
++++++++++
.. autoclass:: joule.api.StreamInfo
    :members:

Element
+++++++

.. autoclass:: joule.api.Element
    :members:

Module
++++++

.. autoclass:: joule.api.Module
    :members:

Errors
++++++

.. autoclass:: joule.errors.SubscriptionError
.. autoclass:: joule.errors.ConfigurationError

Utilities
+++++++++

.. automodule:: joule.utilities
    :members: time_now, timestamp_to_human, unix_to_timestamp, timestamp_to_unix, yesno


