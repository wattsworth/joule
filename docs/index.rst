.. Joule documentation master file, created by
   sphinx-quickstart on Fri Jan  6 17:16:21 2017.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.


Joule: Decentralized Data Processing
====================================

Joule is a framework for decentralized data processing. Joule
distributes computation into independent executable ``modules`` that are
connected by timestamped data flows called
``streams``. Streams can connect modules executing on any device in the
network enabling complex pipelines that distribute computation from edge
nodes all the way to the data center.

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

See the :ref:`getting-started` for quick introduction. Then read
:ref:`using-joule` for an overview of how the system works.

Contributing & Running Tests
----------------------------
Contribution is always welcome. Please include tests with your pull request.
Unittests can be run using nose2, see **joule/htmlcov** for code coverage.

.. code-block:: bash

		$> cd joule
		$> nose2 # run all unittests

End to end tests are run from the ``tests/e2e`` directory and require
docker-compose and the NilmDB container. See
https://docs.docker.com/compose/install/ for details on installing
docker-compose. The NilmDB container is available by request on `Docker Hub`_.

.. code-block:: bash

		$> cd test/e2e
		$> ./runner.sh # run end-to-end tests

.. _Docker Hub: https://hub.docker.com/


.. toctree::
   :maxdepth: 3

   getting_started
   using_joule
   reader_modules
   filter_modules
   composite_modules
   streams
   integration_testing
   nilmdb
   reference
