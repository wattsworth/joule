============
NILM Modules
============

NILM modules provides a suite of reader and filter modules for
non-intrusive power monitors. The system is designed to be run using
a YAML configuration file located at **/opt/configs/meters.yml** although
the modules can be configured to run independently.

Installation
------------
NILM Modules is accessible from the Wattsworth git repository. Contact
donnal@usna.edu to request access.  From the terminal, run the
following commands to install and configure NILM Modules


.. code-block:: bash

   $> git clone https://git.wattsworth.net/wattsworth/nilm.git
   $> cd nilm
   $> sudo python3 setup.py install


Configuration
-------------
Set up a **meters.yml** file according to the guidelines at wattsworth.net for a `contact meter`_
or a `noncontact meter`_. Then run the following from the command line

.. code-block:: bash

		$> nilm configure

This will install stream and module configurations into **/etc/joule/**. Each NILM meter
will have four streams located in **/meter#**

.. code-block:: none

		/meter#/sensor
		  float32 stream of raw ADC sensor values
		/meter#/iv
		  current and voltage at the sample rate of the sensor
		/meter#/sinefit
		  zero crossings of the voltage waveform (freq, amplitude, offset)
		/meter#/prep-a
		/meter#/prep-b
		/meter#/prep-c
		  harmonic envelopes of real and reactive power for each phase
		
Each NILM has a reader module **meter#_capture** and a filter module
**meter#_process**. The modules read configuration values from the
**meters.yml** file.


Verify Operation
----------------
To begin using the newly installed modules restart the **jouled** service by
running the following command:

.. code-block:: bash

		$> sudo systemctl restart joule.service

Verify that the modules are running using the **joule modules** command.

.. code-block:: bash

  $> joule modules
  +--------------------------------+----------------+-----------------+---------+-----+--------------+
  | Module                         | Sources        | Destinations    | Status  | CPU | mem          |
  +--------------------------------+----------------+-----------------+---------+-----+--------------+
  | meter4 process:                | /meter4/sensor | /meter4/prep-a  | running | 39% | 30 MB (355%) |
  | reconstruct -> sinefit -> prep |                | /meter4/prep-b  |         |     |              |
  |                                |                | /meter4/prep-c  |         |     |              |
  |                                |                | /meter4/iv      |         |     |              |
  |                                |                | /meter4/sinefit |         |     |              |
  | meter4 capture:                |                | /meter4/sensor  | running | 8%  | 28 MB (336%) |
  | serial data capture            |                |                 |         |     |              |
  +--------------------------------+----------------+-----------------+---------+-----+--------------+

Any errors will be reported in the log files for each module. Use the
**joule logs** command to print recent log entries. The logs are
automatically rotated: see the ProcDB:MaxLogLines parameter in :ref:`main.conf`

.. code-block:: bash

		   $> joule logs "meter4 capture"
		   [23 Jan 2017 16:14:56] ---starting module---
		   $> joule logs "meter4 process"
		   [23 Jan 2017 16:14:56] ---starting module---

Check that the data is entering NilmDB using the **nilmtool** command. Joule inserts data periodically, see NilmDB:InsertionPeriod in :ref:`main.conf`

.. code-block:: bash
		
   $> nilmtool list -En /meter4/prep*
   /meter4/prep-a
     interval extents: Mon, 23 Jan 2017 16:11:01.833447 -0500 -> Mon, 23 Jan 2017 16:16:29.322283 -0500
           total data: 18054 rows, 300.878769 seconds
   /meter4/prep-b
     interval extents: Mon, 23 Jan 2017 16:11:01.833447 -0500 -> Mon, 23 Jan 2017 16:16:29.322283 -0500
           total data: 18054 rows, 300.878769 seconds
   /meter4/prep-c   /meter4/prep-a
     interval extents: Mon, 23 Jan 2017 16:11:01.833447 -0500 -> Mon, 23 Jan 2017 16:16:29.322283 -0500
           total data: 18054 rows, 300.878769 seconds

.. _contact meter: https://www.wattsworth.net/help/software#config-contact
.. _noncontact meter: https://www.wattsworth.net/help/software#config-noncontact
