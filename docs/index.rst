.. Joule documentation master file, created by
   sphinx-quickstart on Fri Jan  6 17:16:21 2017.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.


Joule: Decentralized Data Processing
====================================

Joule is a framework for decentralized data processing. Joule
distributes computation into independent executable :ref:`sec-modules` that are
connected by :ref:`sec-pipes` which carry timestamped data flows called
:ref:`sec-streams`.

.. image:: /images/module_stream.png
   :width: 400px
   :align: center

A typical deployment is shown below. Embedded sensors collect high
bandwidth data (module 1) and perform feature extraction locally
(module 2). This lower bandwidth feature data is transmitted to
local nodes that convert this into actionable information by applying
machine learning (ML) models (module 3). Aggregation nodes at the
data center collect streams from a variety of local nodes and perform
more computationally intensive tasks like training new ML models (module 4).

.. image:: /images/pipeline_example.png

See the :ref:`quick-start` for a hands-on introduction with an example data pipeline. Then read
:ref:`configuration-reference` for more detailed information on how to configure Joule for your own pipelines.

Contributing & Running Tests
----------------------------
Contribution is always welcome. Please include tests with your pull request.
Unittests can be run using unittest, see **joule/htmlcov** for code coverage.

.. code-block:: bash

    $> cd joule
    $> python3 -m unittest


.. toctree::
    :maxdepth: 3

    installation
    quick_start
    using_joule
    cli
    modules
    pipes
    api_reference

