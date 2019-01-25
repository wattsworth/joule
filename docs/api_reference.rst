API Reference
-------------

Node
++++

Stuff about the Node class

Folder Actions
''''''''''''''

folder_root
```````````

.. autofunction:: joule.api.Node.folder_root

folder_get
``````````

.. autofunction:: joule.api.Node.folder_get

folder_move
```````````

.. autofunction:: joule.api.Node.folder_move

folder_update
`````````````

.. autofunction:: joule.api.Node.folder_update

folder_delete
`````````````

.. autofunction:: joule.api.Node.folder_delete

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


