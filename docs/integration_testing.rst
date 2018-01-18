
Integration Testing
-------------------

Integration or end-to-end (E2E) tests run your module in a mock environment that
mimics a production system.  Integration tests generally run slower than
unittests but they provide a high degree of assurance that the module
operates correctly. The e2e directory in the example_modules
repository has a complete testing infrastructure that runs your module
in a Docker container. The first time you run the test, you will
be prompted to retrieve the containers from Docker hub,
contact donnal@usna.edu for access credentials. The rest of this section
describes the structure of the e2e directory and how to run the test
framework.

.. raw:: html

	<div class="bash header">e2e directory structure</div>
	<div class="code bash">e2e
	\---bootstrap-inner.py
	    docker-compose.yml
	    main.conf
	    runner.sh
	    test.py
	    module_configs
	    \---reader.conf
	        filter.conf
	    stream_configs
	    \---raw.conf
	        filtered.conf
	</div>

There are a large number of files in the test directory but you only need
to customize a few, the rest are boilerplate testing infrastructure. Run
the tests using the **runner.sh** script:

.. raw:: html

	<div class="bash header">Command Line</div>
	<div class="code bash"><b>$> cd example_modules/e2e</b>
	<b>$> ./runner.sh</b>
	<i>#...output from Docker omitted..</i>
	joule   | ---------[running e2e test suite]---------
	joule   | OK
	e2e_joule_1 exited with code 0
	<i>#...output from Docker omitted...</i>
	</div>

When you run this command, you will see several lines of output from Docker as it sets up the test
environment and then tears down the environment and cleans up. The important lines of output are
shown above. These lines are produced by ``test.py`` which contains all of the testing
logic and is the only file in e2e directory which you should customize. Before writing the tests
though you need to set up the appropriate configuration files to run your module.

Configuration Files
'''''''''''''''''''

The E2E tests run joule just like a production system, therefore you
must include module and stream configuration files in order for joule
to recognize and run your module. These file provide a type of "live"
documentation that others can use as a guide when setting up your module on other their
system.

The example_modules e2e test runs both the reader and filter module. The
reader module configuration is shown below:

.. raw:: html

  <div class="header ini">
  e2e/module_configs/reader.conf
  </div>
	<div class="code ini"><span>[Main]</span>
  <b>exec_cmd =</b> python3 /joule-modules/reader.py 0.1
  <b>name =</b> Demo Reader

  <span>[Inputs]</span>

  <span>[Outputs]</span>
  <b>output =</b> /demo/raw
  </div>

The reader module has no sources and one output called **output**
which is connected to the **/demo/raw** NilmDB stream. Note that the
exec command uses the **python3** interpreter and the module script is in
the **/joule-modules/** directory. The e2e bootstrap process copies
the contents of the project folder into **/joule-modules** on the
test container. If your module scripts are stored in subdirectories
access them at a path like
**/joule-modules/my-subdirectory/module.py**

The filter module has a similar configuration:

.. raw:: html

	<div class="header ini">
	e2e/module_configs/filter.conf
	</div>
	<div class="code ini"><span>[Main]</span>
	<b>exec_cmd =</b> python3 /joule-modules/filter.py 2
	<b>name =</b> Demo Filter

	<span>[Inputs]</span>
	<b>raw =</b> /demo/raw

	<span>[Outputs]</span>
	<b>filtered =</b> /demo/filtered
	</div>

It has one source, **input** which is attached to the NilmDB stream
**/demo/raw**. This stream is produced by the reader module. The
filter has one output, **output** which is attached to the NilmDB
stream **/demo/filtered**. The **exec_cmd** has the same structure as
the reader module. Note that any arguments you added to the
``custom_args`` function in your module should be specified as command
line arguments to the **exec_cmd**.

The stream configurations for both **/demo/filtered** and **/demo/raw**
are in the **stream_configs** directory:

.. raw:: html

  <div class="header ini">
  e2e/stream_configs/raw.conf
  </div>
  <div class="code ini"><span>[Main]</span>
  <b>name</b> = Raw Data
  <b>path</b> = /demo/raw
  <b>datatype</b> = int32
  <b>keep</b> = 1w

  <span>[Element1]</span>
  <b>name</b> = random
  </div>

.. raw:: html

  <div class="header ini">
  e2e/stream_configs/filtered.conf
  </div>
  <div class="code ini"><span>[Main]</span>
  <b>name</b> = Raw Data
  <b>path</b> = /demo/raw
  <b>datatype</b> = int32
  <b>keep</b> = 1w

  <span>[Element1]</span>
  <b>name</b> = filtered
  </div>



test.py
'''''''

This file contains all of the testing logic. This file runs once the
joule process has started and it interrogates the system using the
same tools that would be available to an end user working on a live
installation.

.. code-block:: python

		def main():
		    time.sleep(8)   # wait for jouled to boot and get data
		    check_modules() # these functions use asserts to fail on error
		    check_data()
		    check_logs()

		def check_modules()
		    #check output from 'joule modules' command

		def check_data()
		    #check NilmDB data using 'nilmtool' commands

		def check_logs()
		    #check output from 'joule logs' command

		if __name__ == "__main__":
		    main()
		    print("OK") # no asserts failed, so things are good

Not all of these tests may be necessary for your module, they are included in the
example repository to show the range of tests that are possible rather than a prescription
of exactly which tests to perform. See the contents of **test.py** for several examples
and the e2eutils reference for details on the testing API.
