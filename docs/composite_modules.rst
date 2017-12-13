Composite Modules
=================

Composite modules aggregate multiple modules into a single
process. They may have one or more input streams and one or
more output streams. Composite modules should extend the base
class ``CompositeModule`` illustrated below.

.. image:: /images/composite_module.png

The **Example Modules** repository provides templates for the basic module types as well as
unit and integration testing infrastructure. It is available
on the Wattsworth `Git Repository`_

.. raw:: html

  <div class="header bash">
  Command Line:
  </div>
  <div class="code bash"><b>$> git clone https://git.wattsworth.net/wattsworth/example_modules.git</b>
  <b>$> cd example_modules</b>
  <i># install nose2 and asynctest module to run tests</i>
  <b>$> sudo pip3 install nose2 asynctest</b>
  </div>

Example Composite
-----------------

The contents of ``example_composite.py`` are shown below:

.. _Git Repository: http://git.wattsworth.net/wattsworth/example_modules
.. _structured array: https://docs.scipy.org/doc/numpy-1.13.0/user/basics.rec.html
.. _ArgumentParser: https://docs.python.org/3/library/argparse.html#argparse.ArgumentParser
.. _Namespace: https://docs.python.org/3/library/argparse.html#argparse.Namespace
