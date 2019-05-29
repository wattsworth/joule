Modules can provide web-based user interfaces.
When a Joule node is connected to
a Lumen server, the user authentication and authorization is handled
by Lumen and the interface is presented on a common dashboard with other
modules the user is authorized to use.

To add an interface to a module implement the :meth:`joule.BaseModule.routes` function
and register handlers for any routes your module implements. Then enable the interface
by changing the ``is_app`` attribute to ``yes`` in the
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

Typical web interfaces require more complex HTML, cascading style sheets (CSS), and javascript. The example below
provides a complete module implementation using the `Bootstrap <http://getbootstrap.com/>`_ CSS framework
and `Jinja <http://jinja.pocoo.org/>`_ HTML templates.

.. literalinclude:: /../../example_modules/jouleexamples/bootstrap_interface.py
   :language: python
   :caption: Source: ``example_modules/jouleexamples/bootstrap_interface.py``
   :linenos:

In addition to the module code itself this interface requires several additional files located in the assets directory
as shown:

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

The HTML templates are stored in ``assets/templates``. **layout.jinja2** is common to all views and provides hooks
to customize the content and inject additional stylesheet and script tags. The module home page renders **index.jinja**
which is shown below:

.. literalinclude:: /../../example_modules/jouleexamples/assets/templates/index.jinja2
   :language: jinja
   :caption: Source: ``example_modules/jouleexamples/assets/templates/index.jinja2``
   :linenos:

Notice that additional CSS and javascript assets that are injected into the appropriate blocks in the layout template.
Bootstrap classes provide a simple and powerful mechanism for creating a basic page, but in some cases it may be
necessary to add custom CSS to fine tune an element's appearance.

.. literalinclude:: /../../example_modules/jouleexamples/assets/css/index.css
   :language: css
   :caption: Source: ``example_modules/jouleexamples/assets/css/index.css``
   :linenos:

Javascript makes websites interactive. This file makes repeated calls to the server for new data.
Using AJAX requests rather than reloading the entire page improves the user's experience and reduces network traffic.

.. literalinclude:: /../../example_modules/jouleexamples/assets/js/index.js
   :language: js
   :caption: Source: ``example_modules/jouleexamples/assets/js/index.js``
   :linenos:



Development
'''''''''''

When running as a standalone process, modules that provide a web interface
will start a local webserver on port 8000 (by default). This is accessible
from a browser at ``http://localhost:8000``.