
During development it is often helpful to run modules as standalone
processes in order to use debuggers such as pdb or visualization tools like matplotlib.pyplot.
Filter (and Composite) modules may be executed outside of the Joule environment in
either **live** or **historic** mode. When executed independently the module configuration
file must be provided so that the module can request the appropriate stream connections from
Joule.

.. note::
    The joule service must be running in order to run filters as standalone processes


**Live Isolation**
Connect filter inputs to live streams produced by the current joule pipeline.
Specify the module configuration file and a directory with configurations
for each output stream.

.. raw:: html

  <div class="header bash">
  Command Line:
  </div>

  <div class="code bash"><i># [module.conf] is a module configuration file</i>

  <b>$>./demo_filter.py --module_config=module.conf</b>
  Requesting live stream connections from jouled... [OK]
  <i>#...stdout/stderr output from filter</i>
  <i># hit ctrl-c to stop </i>

  </div>

**Historic Isolation**
Connect filter inputs to a range of stream data saved in NilmDB.

Specify historic execution by including a time range with **--start**
and **--end** arguments. The time range may be a date
string or a Unix microseconds timestamp. Common phrases are also supported
such as "2 hours ago" or "today".

.. warning::

  Running a filter in historic isolation mode will overwrite
  existing output stream data

.. raw:: html

    <div class="header bash">
    Command Line:
    </div>

    <div class="code bash"><i># [module.conf] is a module configuration file</i>

    <b>$>./demo_filter.py --module_config=module.conf \
        --start="yesterday" --end="1 hour ago"</b>
    Requesting historic stream connections from jouled... [OK]
    <i>#...stdout/stderr output from filter</i>

    <i># program exits after time range is processed </i>

    </div>
