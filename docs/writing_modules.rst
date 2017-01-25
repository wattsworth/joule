.. _writing_modules:

===============
Writing Modules
===============

Modules are standalone processes managed by Joule. They are
connected to eachother and to the backing NilmDB datastore by
streams. Modules can have zero or more input streams and one or more
output streams. Joule does not impose any additional constraints on
modules but we recommend structuring modules using the reader
and filter patterns. See :ref:`joule-concepts` for more details.

The first two sections below show you how to write a custom reader or
filter by extending the **ReaderModule** and **FilterModule**
built-ins. This is recommended for most use cases. If your
module requires siginificant customization, see custom modules for
writing a module from scratch and advanced modules for techniques to
optimize module performance.

A template repository is available at <> with a starter filter
and starter reader module. This repository also contains a testing
infrastructure for both types of modules. Proper testing is critical
to designing complex modules, especially filters.

Extending ReaderModule
----------------------
how to implement a custom reader


Extending FilterModule
----------------------
how to implement a custom filter


Custom Modules
--------------
writing modules from scratch


Advanced Modules
----------------
using local numpy pipes
