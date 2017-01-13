============
Installation
============

Joule requires NilmDb for stream storage [#f1]_. The other dependency is Python 3.5. On distros
that do not ship with Python 3.5 such as Raspbian it must be built from source.


Install NilmDb
--------------------
NilmDb is accessible form the Wattsworth git repository. Contact donnal@usna.edu to request access.
From the terminal, run the following commands to install and configure NilmDb.


Install dependencies

.. code-block:: bash

 $> sudo apt-get install cython git build-essential \		
      python2.7 python2.7-dev python-setuptools python-pip \
      python-cherrypy3 python-decorator python-requests \
      python-dateutil python-tz python-progressbar python-psutil \
      python-simplejson
 $> sudo apt-get install apache2 libapache2-mod-wsgi
   
Install NilmDb

.. code-block:: bash

   $> git clone https://git.wattsworth.net/nilm/nilmdb.git
   $> cd nilmdb
   $> sudo python setup.py install

*Configure WSGI Scripts*

Create a directory for NilmDB (eg **/opt/nilmdb**), in this directory create a file
**nilmdb.wsgi** as shown below:

.. code-block:: python
   
   import nilmdb.server
   application = nilmdb.server.wsgi_application("/opt/nilmdb/db","/nilmdb")

This will create a virtual host at **http://localhost/nilmdb** with data stored
in the directory **/opt/nilmdb/db**. Now create a user to run Nilmdb and give them
permissions on the directory:

.. code-block:: bash

   $> adduser nilmdb
   $> chown -R nilmdb:nilmdb /opt/nilmdb
   
*Configure Apache*

Edit the default virtual host configuration at **/etc/apache2/site-available/000-default** to add the following lines within the ``<VirtualHost>`` directive:

.. code-block:: apache

  <VirtualHost *:80>
    # Add these 6 lines
    WSGIScriptAlias /nilmdb /home/nilmdb/nilmdb.wsgi
    WSGIDaemonProcess nilmdb-procgroup threads=32 user=nilmdb group=nilmdb
    <Location /nilmdb>
      WSGIProcessGroup nilmdb-procgroup
      WSGIApplicationGroup nilmdb-appgroup
    </Location>
    # (other existing configuration here)
  </VirtualHost>

Note these values assume you followed the user creation and file naming guidelines above.

Docker
^^^^^^

NilmDb is also available as a Docker container available through Docker Hub. E-mail donnal@usna.edu for access.

.. code-block:: bash

   $> docker pull jdonnal/nilmdb




Install Python 3.5
------------------

Joule requires Python 3.5 or greater. As of this writing many distros including
Raspbian ship with earlier versions.  Check your version by running
the following command:

.. code-block:: bash

  $> python3 -V
  Python 3.5.2   #<--- this version is ok
  

Install Dependencies

.. code-block:: bash
		
 $> sudo apt-get install build-essential tk-dev  

Download and Install Source

.. code-block:: bash
		
 $> wget https://www.python.org/ftp/python/3.5.2/Python-3.5.2.tgz
 $> tar -xvf Python-3.5.2.tgz
 $> cd Python-3.5.2
 $> ./configure
 $> make
 $> sudo make install

This will install python3.5 into **/usr/local/bin**

VirtualEnv
^^^^^^^^^^

You may optionally install Joule into a virtual environment, this is
recommended if you expect Joule to conflict with other Python tools
you already have installed. The easiest way to work with virtual
environments is with *virtualenvwrapper*

.. code-block:: bash
		
 $> pip install virtualenv virtualenvwrapper
 $> export WORKON_HOME=~/Envs
 $> source /usr/local/bin/virtualenvwrapper.sh

(`Full virtualenvwrapper install instructions. <https://virtualenvwrapper.readthedocs.io/en/latest/install.html>`_)
 
Create a new virtual environment using Python 3.5

.. code-block:: bash
		
 $> mkvirtualenv joule -p 3.5
 $> workon joule


Install Joule
-------------

Joule is accessible form the Wattsworth git repository. Contact
donnal@usna.edu to request access. From the terminal, run the
following commands to install and configure Joule.

.. code-block:: bash

 $> git clone https://git.wattsworth.net/wattsworth/joule.git
 $> cd joule
 $> python3 setup.py install

Configure Joule

By default joule looks for configuration files at **/etc/joule**. Run the following commands
to create the basic directory structure

.. code-block:: bash

 $> sudo mkdir -p /etc/joule/module_configs
 $> sudo mkdir -p /etc/joule/stream_configs
 $> sudo touch /etc/joule/main.conf
 
Create Startup Scripts



Verify Installation
-------------------


.. [#f1] A local installation of NilmDb is not strictly necessary as all
   communication between Joule and NilmDb occurs over HTTP but sending
   all stream data over a network connection to a remote NilmDb instance  
   may impact performance.

.. [#f2] These commands assume **python3** points to a Python
   3.5 or later instance. If your system **python3** is earlier than 3.5
   work in a virtual environment or adjust your environment to reference
   the python3.5 binaries in **/usr/local/bin/**
