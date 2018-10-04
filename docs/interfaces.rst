Modules can provide web-based user interfaces.
When a Joule node is connected to
a Lumen server, the user authentication and authorization is handled
by Lumen and the interface is presented on a common dashboard with other
modules the user is authorized to use.

To add an interface to a module implement the :meth:`joule.BaseModule.routes` function
and register handlers for any routes your module implements. Then enable the interface
by changing the ``has_interface`` attribute to ``yes`` in the
:ref:`sec-modules` file.

Examples
''''''''

Basic Interface
^^^^^^^^^^^^^^^

.. literalinclude:: /../../example_modules/jouleexamples/example_interface.py
   :language: python
   :caption: Source: ``example_modules/jouleexamples/example_interface.py``
   :linenos:

Bootstrap Interface
^^^^^^^^^^^^^^^^^^^

Typical web interfaces require more complex HTML, cascading style sheets (CSS) for data
presentation, and javascript for interactive page elements. The example below illustrates

A more pratical interface is shown be
.. literalinclude:: /../../example_modules/jouleexamples/bootstrap_interface.py
   :language: python
   :caption: Source: ``example_modules/jouleexamples/bootstrap_interface.py``
   :linenos:

.. code-block:: none
    :caption: file layout for ComplexInterface assets

    ├── bootstrap_interface.py
    └── assets
        ├── css
        │   └── main.css # and other css files
        ├── js
        │   └── index.js # other js files
        └── templates
            ├── layout.jinja2
            └── index.jinja2

.. literalinclude:: /../../example_modules/jouleexamples/assets/templates/index.jinja2
   :language: jinja
   :caption: Source: ``example_modules/jouleexamples/assets/templates/index.jinja2``
   :linenos:

.. literalinclude:: /../../example_modules/jouleexamples/assets/css/index.css
   :language: css
   :caption: Source: ``example_modules/jouleexamples/assets/css/index.css``
   :linenos:

.. literalinclude:: /../../example_modules/jouleexamples/assets/js/index.js
   :language: js
   :caption: Source: ``example_modules/jouleexamples/assets/js/index.js``
   :linenos:



Development
'''''''''''

When running as a standalone process, modules that provide a web interface
will start a local webserver on port 8000 (by default). This is accessible
from a browser at ``http://localhost:8000``.