Command Line Interface
----------------------

``jouled`` -- controls pipeline execution, runs as a system daemon

  .. raw:: html

    <div class="header bash">
    Command Line:
    </div>
    <div class="code bash"><i># use service to control jouled:</i>
    <i># NOTE: restart the service to apply configuration file changes</i>
    <b>$>sudo service jouled</b> [start|stop|restart|status]

    <i># by default jouled starts at boot, this can be enabled or disabled:</i>
    <b>$>sudo systemctl</b> [enable|disable] <b>jouled.service</b>

    <i># jouled may be run in the foreground if the service is stopped</i>
    <b>$> sudo jouled</b>
    <i># exit with Ctrl-C</i>
    </div>

``joule modules`` -- view currently executing modules

  .. raw:: html

      <div class="header bash">
      Command Line:
      </div>
      <div class="code bash"><b>$>joule modules</b>
      +-------------+--------------+----------------+---------+-----+
      | Module      | Inputs      | Outputs   | Status  | CPU |     |
      +-------------+--------------+----------------+---------+-----+
      | Demo Reader |              | /demo/random   | running | 0%  |
      | Demo Filter | /demo/random | /demo/smoothed | running | 0%  |
      +-------------+--------------+----------------+---------+-----+
      </div>


``joule logs`` -- view stdout and stderr from a module

  Joule keeps a rolling log of module output. By default the last 100 lines
  are stored, see :ref:`sec-system-configuration` to customize
  this value.

  .. raw:: html

      <div class="header bash">
      Command Line:
      </div>
      <div class="code bash"><b>$>joule logs "Demo Filter"</b>
      [27 Jan 2017 18:22:48] ---starting module---
      [27 Jan 2017 18:22:48] Starting moving average filter with window size 9
      #... additional output
      </div>
