.. _modules:

Modules
-------

Modules are executable programs that process data :ref:`streams`. They are
connected to each other by :ref:`pipes`. Joule runs each module as a separate
process. This enforces isolation and improves resiliency.
Malfunctioning modules do not affect other parts of the pipeline
and can be restarted without interrupting the data flow. There are three basic types:
:ref:`sec-reader`, :ref:`sec-filter`, and :ref:`sec-composite`.

Examples in the documentation below are available at http://git.wattsworth.net/wattsworth/example_modules.
This repository provides templates for the basic module types as well as
unit and integration testing infrastructure.

.. raw:: html

  <div class="header bash">
  Command Line:
  </div>
  <div class="code bash"><b>$> git clone https://git.wattsworth.net/wattsworth/example_modules.git</b>
  <b>$> cd example_modules</b>
  <i># install nose2 and asynctest module to run tests</i>
  <b>$> sudo pip3 install nose2 asynctest</b>
  </div>

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


.. _sec-filter:

Filter Modules
++++++++++++++

Filter modules process data. They may have one or more input streams and one or
more output streams. Filter modules should extend the base class :class:`joule.FilterModule` illustrated below.

.. image:: /images/filter_module.png


Examples
''''''''

.. include:: filter_module/example.rst

Development
'''''''''''

.. include:: filter_module/development.rst

Testing
'''''''

.. include:: filter_module/testing.rst

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

