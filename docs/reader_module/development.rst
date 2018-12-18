
During development it is often helpful to run the reader module as a standalone
process in order to use debuggers such as pdb or visualization tools like matplotlib.pyplot.
When a reader module is executed from the command line the output pipe is connected to stdout:

.. raw:: html

  <div class="header bash">
  Command Line:
  </div>
  <div class="code bash"><b>$>./demo_reader.py</b>
  1485188853650944 0.32359053067687582 0.70028608966895545
  1485188853750944 0.72139550945715136 0.39218791387411422
  1485188853850944 0.40728044378612194 0.26446072057019654
  1485188853950944 0.61021957330250398 0.27359526775709841
  <i># hit ctrl-c to stop </i>

  </div>


If the ``--module_config``
argument is specified the output pipe is instead connected to the stream specified in the configuration
file. The stream will be created if it does not exist. By default the module will connect to the local
joule server, use the ``--url`` option to connect to a specific joule server. Any arguments
in the configuration file will be parsed as if they were specified on the command line.


.. raw:: html

  <div class="header bash">
  Command Line:
  </div>
  <div class="code bash"><b>$>./demo_reader.py --module_config=module.conf</b>
  Contacting joule server at http://localhost:8080
  <i># hit ctrl-c to stop </i>

  </div>