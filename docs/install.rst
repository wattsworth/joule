.. _installing-joule:

============
Installation
============

Joule requires NilmDb for stream storage [#f1]_. The other dependency is Python 3.5. On distros
that do not ship with Python 3.5 such as Raspbian it must be built from source.


Install NilmDb
--------------------

NilmDb is accessible from the Wattsworth git repository. Contact
donnal@usna.edu to request access.  From the terminal, run the
following commands to install and configure NilmDb.


Install dependencies

.. code-block:: bash

		$> sudo apt-get update
		$> sudo apt-get install cython git build-essential \		
		python2.7 python2.7-dev python-setuptools python-pip \
		python-cherrypy3 python-decorator python-requests \
		python-dateutil python-tz python-progressbar python-psutil \
		python-simplejson apache2 libapache2-mod-wsgi -y

   
Install NilmDb

.. code-block:: bash
		
		$> git clone https://git.wattsworth.net/wattsworth/nilmdb.git
		$> cd nilmdb
		$> sudo make install

*Configure WSGI Scripts*

Create a directory for NilmDB (eg **/opt/nilmdb**), in this directory
create a file **nilmdb.wsgi** as shown below:

.. code-block:: python
   
   import nilmdb.server
   application = nilmdb.server.wsgi_application("/opt/nilmdb/db","/nilmdb")

This will create a virtual host at **http://localhost/nilmdb** with data stored
in the directory **/opt/nilmdb/db**. Now create a user to run Nilmdb and give them
permissions on the directory:

.. code-block:: bash

   $> adduser nilmdb
   $> sudo chown -R nilmdb:nilmdb /opt/nilmdb
   
*Configure Apache*

Edit the default virtual host configuration at
**/etc/apache2/site-available/000-default** to add the following lines
within the ``<VirtualHost>`` directive:

.. code-block:: apache

  <VirtualHost *:80>
    # Add these 6 lines
    WSGIScriptAlias /nilmdb /opt/nilmdb/nilmdb.wsgi
    WSGIDaemonProcess nilmdb-procgroup threads=32 user=nilmdb group=nilmdb
    <Location /nilmdb>
      WSGIProcessGroup nilmdb-procgroup
      WSGIApplicationGroup nilmdb-appgroup
      Require all granted	  
    </Location>
    # (other existing configuration here)
  </VirtualHost>

Note these values assume you followed the user creation and file
naming guidelines above.

*Test the Installation*

Restart Apache to start the NilmDB server, then check the database is
available using the **nilmtool** command.

.. code-block:: bash

   $> sudo apache2ctl restart
   $> nilmtool info
   Client version: 1.10.3
   #...more information

Docker
^^^^^^

NilmDb is also available as a container through
Docker Hub.  E-mail donnal@usna.edu for access. See the `docker homepage
<https://www.docker.com/>`_ for
more information on containers.

.. code-block:: bash

   $> docker pull jdonnal/nilmdb




Install Python 3.5
------------------

Joule requires Python 3.5 or greater. As of this writing many distros including
Raspbian ship with earlier versions.  Check your version by running
the following command:

.. code-block:: bash

  $> sudo apt-get install python3 python3-pip -y
  $> python3 -V
  Python 3.5.2   #<--- this version is ok
  
If your version is 3.5.2 or greater, skip ahead to installing Joule, otherwise you
must build Python 3.5 from source by following the instructions below:

Install Dependencies

.. code-block:: bash
		
 $> sudo apt-get install build-essential tk-dev libssl-dev libblas-dev  \
 liblapack-dev libbz2-dev gfortran libsqlite3-dev

Download and Install Source

.. code-block:: bash
		
 $> wget https://www.python.org/ftp/python/3.5.2/Python-3.5.2.tgz
 $> tar -xvf Python-3.5.2.tgz
 $> cd Python-3.5.2
 $> ./configure
 $> make
 $> sudo make install

This will install python3.5 into **/usr/local/bin**

Install matplotlib, numpy and scipy. These must be built from source so you need to 
get the dependencies before running pip. Edit ``/etc/apt/sources.list`` to include a 
source entry like ``deb-src``. Then run the following commands:

.. code-block:: bash

   $> sudo apt-get build-dep python3-scipy python3-numpy python3-matplotlib
   $> sudo pip3 install numpy matplotlib scipy
VirtualEnv
^^^^^^^^^^

You may optionally install Joule into a virtual environment, this is
recommended if you expect Joule to conflict with other Python tools
you already have installed. The easiest way to work with virtual
environments is with *virtualenvwrapper*

.. code-block:: bash
		
 $> pip2 install virtualenv virtualenvwrapper
 $> export WORKON_HOME=~/Envs
 $> source /usr/local/bin/virtualenvwrapper.sh

(`Full virtualenvwrapper install
instructions. <https://virtualenvwrapper.readthedocs.io/en/latest/install.html>`_)
 
Create a new virtual environment using Python 3.5

.. code-block:: bash
		
 $> mkvirtualenv joule -p /usr/local/bin/python3.5 #<-- path to 3.5 installation
 $> workon joule


Install Joule
-------------

Joule is accessible form the Wattsworth git repository. Contact
donnal@usna.edu to request access. From the terminal, run the
following commands to install and configure Joule.

.. code-block:: bash

		# install dependencies
		# if python3.5 was installed from source you must specify the correct pip
		# (ie /usr/local/bin/pip3.5 instead of pip3)
		$> pip3 install --upgrade pip # make sure pip is up to date
		$> pip3 install python-datetime-tz
		$> apt-get install python3-numpy python3-scipy python3-yaml -y
		
.. code-block:: bash

		# install Joule
		$> git clone https://git.wattsworth.net/wattsworth/joule.git
		$> cd joule
		$> python3 setup.py install

*Configure Joule*

By default joule looks for configuration files at **/etc/joule**. Run
the following commands to create the basic directory structure

.. code-block:: bash

 $> sudo mkdir -p /etc/joule/module_configs
 $> sudo mkdir -p /etc/joule/stream_configs
 $> sudo touch /etc/joule/main.conf
 
*Create Startup Scripts*

To configure Joule to run automatically you must add a configuration script to systemd. Copy the following into **/etc/systemd/system/joule.service**

.. code-block:: ini
		
  [Unit]
  Description = "Joule Management Daemon"
  After = syslog.target

  [Service]
  Type = simple
  # **note: path will be different if joule is in a virtualenv**
  ExecStart = /usr/local/bin/jouled 
  StandardOutput = journal
  StandardError = journal
  Restart = always

  [Install]
  WantedBy = multi-user.target

To enable and start the joule service run

.. code-block:: bash

   $> sudo systemctl enable joule.service
   $> sudo systemctl start joule.service
   

Verify Installation
-------------------

Check that joule is running:

.. code-block:: bash

   $> sudo systemctl status joule.service
   ● joule.service - "Joule Management Daemon"
      Loaded: loaded (/etc/systemd/system/joule.service; enabled)
      Active: active (running) since Tue 2017-01-17 09:53:21 EST; 7s ago
   Main PID: 2296 (jouled)
     CGroup: /system.slice/joule.service
             └─2296 /usr/local/bin/python3 /usr/local/bin/jouled

Joule is managed from the terminal using the **joule** command, on a fresh
installation there is nothing for Joule to do so these commands will not return
data. Check that they are available by printing the help output.

.. code-block:: bash

   $> joule modules -h
      # ... some help text
   $> joule logs -h
      # ... some help text

Your Joule installation should be ready to go, read
:ref:`getting-started` to configure your first module and start
capturing data.


.. [#f1] A local installation of NilmDb is not strictly necessary as all
   communication between Joule and NilmDb occurs over HTTP but sending
   all stream data over a network connection to a remote NilmDb instance  
   may impact performance.

.. [#f2] These commands assume **python3** points to a Python
   3.5 or later instance. If your system **python3** is earlier than 3.5
   work in a virtual environment or adjust your environment to reference
   the python3.5 binaries in **/usr/local/bin/**
