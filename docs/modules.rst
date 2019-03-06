.. _modules:

Modules
-------

Modules are executable programs that process data :ref:`sec-streams`. They are
connected to each other by :ref:`pipes`. Joule runs each module as a separate
process. This enforces isolation and improves resiliency.
Malfunctioning modules do not affect other parts of the pipeline
and can be restarted without interrupting the data flow. There are three basic types:
:ref:`sec-reader`, :ref:`sec-filter`, and :ref:`sec-composite`.

Examples in the documentation below are available at https://github.com/wattsworth/example-modules.git
This repository provides serveral examples of each module types and can be used as a template
to design your own installable Joule modules.

.. raw:: html

  <div class="header bash">
  Command Line:
  </div>
  <div class="code bash"><b>$> git clone https://github.com/wattsworth/example-modules.git</b>
  <i># To install modules system-wide: </i>
  <b>$> python3 setup.py install </b>
  <i># To run unittests: </i>
  <b>$> python3 setup.py tests</b>
  </div>

The layout of the repository is shown below.

.. code-block:: none

    example_modules/
    ├── jouleexamples
    │   ├── example_composite.py
    │   ├── example_filter.py
    │   ├── example_reader.py
    │   └── ... other modules
    ├── module_configs
    │   ├── example_composite.conf
    │   ├── example_filter.conf
    │   ├── example_reader.conf
    │   └── ... other module configs
    ├── README.rst
    └── stream_configs
        └── ... stream config examples

.. _sec-reader:

Reader Modules
++++++++++++++

Reader modules are designed to read data into the Joule Framework. Data can come from
sensors, system logs, HTTP API's or any other timeseries data source. Reader modules
should extend the base class :class:`joule.ReaderModule` illustrated below.

.. image:: /images/reader_module.png


Examples
''''''''

.. include:: reader_module/example.rst

Development
'''''''''''

.. include:: reader_module/development.rst

Testing
'''''''

.. include:: reader_module/testing.rst

Reference
'''''''''

.. autoclass:: joule.ReaderModule
    :members:
    :inherited-members:

.. _sec-filter:

Filter Modules
++++++++++++++

Filter modules process data. They may have one or more input streams and one or
more output streams. Filter modules should extend the base class :class:`joule.FilterModule` illustrated below.

.. image:: /images/filter_module.png


Examples
''''''''

.. include:: filter_module/example.rst

.. _sec-filter-development:

Development
'''''''''''

.. include:: filter_module/development.rst

.. _sec-filter-testing:

Testing
'''''''

.. include:: filter_module/testing.rst

Reference
'''''''''

.. autoclass:: joule.FilterModule
    :members:
    :inherited-members:

.. _sec-composite:

Composite Modules
+++++++++++++++++


Composite modules aggregate multiple modules into a single
process. They may have one or more input streams and one or
more output streams. Composite modules should extend the base
class :class:`joule.CompositeModule` illustrated below.

.. image:: /images/composite_module.png

Examples
''''''''

.. include:: composite_module/example.rst

Development
'''''''''''

.. include:: composite_module/development.rst

Testing
'''''''

.. include:: composite_module/testing.rst

Reference
'''''''''

.. autoclass:: joule.CompositeModule
    :members:
    :inherited-members:

User Interfaces
+++++++++++++++

.. include:: interfaces.rst