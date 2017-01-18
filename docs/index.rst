.. Joule documentation master file, created by
   sphinx-quickstart on Fri Jan  6 17:16:21 2017.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

   
Joule: Modular Data Processing
=================================


Joule is a data capture and signal processing engine. It allows you to
turn a single board computer like the Raspberry Pi into a robust
sensor platform. Joule uses modules to build complex acquisition and
signal processing workflows from simple building blocks.  Modules are
user defined processes that are connected together by data streams.

Joule acts as a process manager, ensuring that modules start at system
boot and are restarted if they fail. Joule also collects runtime
statistics and logs for each module making it easy to detect
bugs and find bottlenecks in processing pipelines.


.. toctree::
   :maxdepth: 2
      
   concepts
   install
   getting_started
   writing_modules
   nilm

                                             
Tutorial
--------

Let's install everything and get it up and running

Usage Documentation
-------------------

Here's how to use it

API Documentation
-----------------

Contributing & Running Tests
----------------------------

