.. _configuration-reference:

Configuration
=============


Joule decentralizes signal processing into discrete **modules**. These
modules are connected by **streams** as shown in the figure below. The
interconnection of modules and streams form a data **pipeline**. A pipeline may execute
as a single proces, a collection of processes, or even be distributed
across multiple nodes in a network without adjusting any module code.

.. figure:: /images/data_pipeline.png

   Joule **pipelines** are composed of **modules** and **streams**

Joule is a system service. Use the ``joule`` command to interact with the service.

.. raw:: html

    <div class="bash-code">

    # joule is a systemd service
    $> sudo service joule restart

    # use journalctl to view joule logs
    $> sudo journalctl -u joule.service
    ... journalctl output

    # use the joule CLI to interact with the service
    $> joule --help
    Usage: joule [OPTIONS] COMMAND [ARGS]...

    </div>

Joule constructs the pipeline based on configuration files in **/etc/joule**. Details on these
configuration files is provided in the sections below.

.. _sec-modules:

Module Configuration
--------------------

:ref:`modules` are executable programs managed by Joule. The module configuration format is shown below:

.. raw:: html

    <div class="config-file">

    : Module Configuration File

    [Main]
    #required
    name = module name
    exec_cmd = /path/to/executable
    #optional
    is_app = no
    description = a short description

    # Specify command line arguments
    # (may also include in the exec_cmd)
    [Arguments]
    arg1 = val1
    arg2 = val2
    # additional arguments...

    [Inputs]
    path1 = /data/input/stream1
    path2 = /data/input/stream2
    # additional inputs...

    [Outputs]
    path1 = /data/output/stream1
    path2 = /data/output/stream2
    # additional outputs...

    </div>


Module configuration files must end with the **.conf** suffix and should be placed in
**/etc/joule/module_configs**. See the list below for information on each setting.
Only the **[Main]** section is required, other sections should be included as necessary.

**[Main]**
  * ``exec_cmd`` -- path to module executable, may include command line arguments
  * ``name`` -- module name
  * ``is_app`` -- **[yes|no]** whether the module provides a web interface
  * ``description`` -- optional module description

**[Arguments]**
  * ``key = value`` -- keyword arguments (these may also be specified in the ``exec_cmd``)

**[Inputs]**
  * ``name = /stream/path`` -- input :ref:`sec-pipes`

**[Outputs]**
  * ``name = /stream/path`` -- output pipe configuration

Note: Reader Modules may only have a single output and no inputs. Filter modules have no restrictions on the number
of inputs and outputs.

.. _sec-pipes:

Pipe Configuration
------------------

:ref:`pipes` connect modules to data streams and are configured in the **[Inputs]** and **[Outputs]** section of the :ref:`sec-modules`
file. At a minimum the configuration specifies a pipe name and a stream path shown in Example 1 below.

.. raw:: html

    <div class="config-file">

    : Pipe Configuration Format

    #1. basic configuration [pipe name] = [stream path]
    simple = /stream/path/simple

    #2. with inline stream configuration
    inline = /stream/path/inline:float32[x,y,z]

    #3. remote connection, must include inline stream config
    remote = node2.net:8088 /stream/path/remote:float32[x,y,z]

    </div>

The pipe configuration can also include an inline stream configuration. This can be used in place of a :ref:`sec-data-streams`
file or in addition to it. Using both enables static type checking for the pipeline. The inline configuration is
separated from the stream path by a colon ``:``. The stream datatype is followed by a list of comma separated element names
enclosed with brackets ``[ ]``. If
the stream is not explicitly configured or does not already exist in the database it is created with default
attributes. In Example 2 above the ``inline`` pipe is connected to ``/stream/path/inline``
which has three ``float32`` elements named ``x``, ``y``, and ``z``. If this stream already exists
with a different datatype or number of elements, Joule will not start the module.

Pipes can also connect to remote streams. To specify a remote source or destination add the URL and optional port
number before the stream path. The URL is separated from the stream path by a single space. Remote pipes must include an inline stream configuration.
In example 3 above the ``remote`` pipe is connected to ``/stream/path/remote`` on ``node2.net``. If this stream does not
exist on **node2**, it will be created with default attributes. If it does exist with a different datatype, or number of
elements, Joule will not start the module.

Streams can be connected to multiple input pipes but may only be connected to a single output pipe. If a module
attempts to connect an output pipe to a stream that already has a producer, Joule will not start the module.

.. _sec-data-streams:

DataStream Configuration
------------------------

Streams are timestamped data flows. They are composed of one or more elements as shown
below. Timestamps are in Unix microseconds (elapsed time since January 1, 1970).

 ========= ======== ======== === ========
 Timestamp Element1 Element2 ... ElementN
 ========= ======== ======== === ========
 1003421   0.0      10.5     ... 2.3
 1003423   1.0      -8.0     ... 2.3
 1003429   8.0      12.5     ... 2.3
 1003485   4.0      83.5     ... 2.3
 ...       ...      ...      ... ...
 ========= ======== ======== === ========

The configuration format is shown below:

.. raw:: html

  <div class="config-file">

  : DataStream Configuration File

  [Main]
  #required settings (examples)
  name = stream name
  path = /stream/path
  datatype = float32
  keep = 1w

  #optional settings (defaults)
  decimate = yes

  [Element1]
  #required settings (examples)
  name         = stream name

  #optional settings (defaults)
  plottable    = yes
  display_type = continuous
  offset       = 0.0
  scale_factor = 1.0
  default_max  = None
  default_min  = None

  #additional elements...

  </div>

DataStream configuration files must end with the **.conf** suffix and should be placed in
**/etc/joule/data_stream_configs**. Both **[Main]** and **[Element1]** are required.
For streams with more than one element include additional sections **[Element2]**, **[Element3]**, etc.
See the list below for information on each setting.

**[Main]**
  * ``name`` -- stream identifier, white space is permitted
  * ``path`` -- unique identifier which follows the Unix file naming convention. The web UI
    visualizes the path as a folder hierarchy.
  * ``datatype`` -- element datatype. Valid types for TimeScale backend (default):

    .. csv-table::

      float32, int16
      float64, int32
      ,        int64


  * ``keep`` -- how long to store stream data. Format is a value and unit.
    Units are **h**: hours, **d**: days, **w**: weeks, **m**: months, **y**: years.
    For example **6d** will keep the last six days of data. Specify **None**
    to keep no data or **all** to keep all data.

  * ``decimate`` -- **[yes|no]** whether decimated data will be stored for this stream. Decimation
    roughly doubles the required storage but enables web UI visualization.

**[Element#]**
  * ``name`` -- element identifier, may contain whitespace
  * ``plottable`` -- **[yes|no]** whether the element can be plotted
  * ``display_type`` -- **[continuous|discrete|event]** controls the plot type
  * ``offset``-- apply linear scaling to data visualization **y=(x-offset)*scale_factor**
  * ``scale_factor``-- apply linear scaling to data visualization **y=(x-offset)*scale_factor**
  * ``default_max``-- control axis scaling, set to None for auto scale
  * ``default_min``-- control axis scaling, set to None for auto scale

Streams may also be configured using an abbreviated inline syntax in a module's :ref:`sec-pipes`.

.. _sec-event-streams:

EventStream Configuration
-------------------------

Event streams represent asynchronous data with discrete start and end timestamps. Events
may have one or more fields of data, it is recommended but not required to type these fields. Typed fields
facilitate data visualization in Lumen and allow viewing event data with CLI tools.

The configuration format is shown below:

.. raw:: html

  <div class="config-file">

  : EventStream Configuration File

  [Main]
  #required settings
  name = stream name
  path = /stream/path
  keep = 1w

  #optional settings
  description = more info about the stream

  # Field list is optional but if specified cannot be modified by the API

  [Field1]
  name = field name
  type = string | numeric | category:["cat1","cat2",...]

  #additional fields...

  </div>

EventStream configuration files must end with the **.conf** suffix and should be placed in
**/etc/joule/event_stream_configs**. Only the **[Main]** section is required. Including **[Field#]** sections
locks the stream configuration and may not be modified by the API. See the list below for information on each setting.

**[Main]**
  * ``name`` -- stream identifier, white space is permitted
  * ``path`` -- unique identifier which follows the Unix file naming convention. The web UI
    visualizes the path as a folder hierarchy.
  * ``keep`` -- how long to store stream data. Format is a value and unit.
    Units are **h**: hours, **d**: days, **w**: weeks, **m**: months, **y**: years.
    For example **6d** will keep the last six days of data. Specify **None**
    to keep no data or **all** to keep all data.
  * ``description`` -- optional stream description

**[Field#]**
  * ``name`` -- field identifier, may contain whitespace
  * ``type`` -- field type. Valid types are **string**, **numeric**, and **category**. The category type
    requires a list of categories in JSON syntax. Items are quoted with ``" "`` and separated with ``,`` and the list should be enclosed with ``[ ]``. 
    For example ``category:["cat1","cat2"]``.

.. _sec-system-configuration:

System Configuration
--------------------

Joule uses a set of default configurations that should work for most
cases. These defaults can be customized by editing
**/etc/joule/main.conf**. Start joule with the **--config** flag to use a configuration file at
an alternate location. The example **main.conf** below shows the
full set of options and their default settings:

.. raw:: html

  <div class="config-file">

  : /etc/joule/main.conf

    #default settings shown
    [Main]
    Name = <randomly generated by initialize script>
    # Module configuration files
    #   files must end with *.conf
    ModuleDirectory = /etc/joule/module_configs

    ### Only files in the configuration directories ending with .conf
    ### are considered, any others are ignored
    
    # DataStream configuration files
    DataStreamDirectory = /etc/joule/stream_configs

    # EventStream configuration files
    EventStreamDirectory = /etc/joule/event_stream_configs

    # Importer configuration files
    ImporterConfigDirectory = /etc/joule/importer_configs

    # Exporter configuration files
    ExporterConfigDirectory = /etc/joule/exporter_configs

    ### These directories must be writable by the joule user
    ### and are only necessary if using importers and/or exporters

    # Importer data directory
    ImporterDataDirectory = /var/run/joule/importer_data

    # Exporter data directory
    ExporterDataDirectory = /var/run/joule/exporter_data

    ### Set an inbox directory to process file uploads,
    ### omit to disable this feature (API uploads only)
    # ImporterInboxDirectory = /opt/joule/import

    # Listen on address
    # set to 0.0.0.0 to listen on all interfaces
    # omit to only listen on UNIX socket
    # IPAddress = 127.0.0.1

    # Listen on port
    # required if IPAddress is specified
    # Port = 8088

    # UNIX Socket directory (must be writable by joule user)
    SocketDirectory = /var/run/joule/sockets


    # PostgreSQL database connection
    # DSN format
    #   username:password@[domain|ip_address]:port/database
    Database = <replace with database credentials>

    # How often to flush stream data to database
    InsertPeriod = 5

    # How often to remove old data (from DataStream keep settings)
    CleanupPeriod = 60

    # How many lines to keep in each module log (rolling)
    MaxLogLines = 100

    # Manager users with a configuration file
    # UsersFile = /etc/joule/users.conf

    # This section enables HTTPS, omit to run server with HTTP.
    # The default configuration produced by [joule admin initialize]
    # creates a self signed certificate and associated key.
    # To prevent MitM attacks, use a PKI to generate credentials

    [Security]

    # X.509 certificate
    Certificate =  /etc/joule/security/server.crt

    # Private key for X.509 certificate
    Key = /etc/joule/security/server.key

    # Optional CA Certificate when using a PKI
    # CertificateAuthority = /etc/joule/security/ca.crt

    [Proxies]
    # forward local sites as joule interfaces
    # list proxies by [site_name = URL] example:
    # NOTE: do not use "localhost", use the 127.0.0.1 address

    # rails_app = http://127.0.0.1:3000

  </div>

See the list below for information on each setting.

  * ``Name`` Node name, a random value is generated by the ``joule admin initialize`` command
  * ``ModuleDirectory`` Absolute path to module configuration files.
    Only files ending with **.conf** will be loaded
  * ``DataStreamDirectory`` Absolute path to data stream configuration files.
    Only files ending with **.conf** will be loaded
  * ``EventStreamDirectory`` Absolute path to event stream configuration files.
    Only files ending with **.conf** will be loaded
  * ``ImporterConfigDirectory`` Absolute path to importer configuration files.
    Only files ending with **.conf** will be loaded
  * ``ExporterConfigDirectory`` Absolute path to exporter configuration files.
    Only files ending with **.conf** will be loaded
  * ``ImporterDataDirectory`` Absolute path to a directory used when processing data imports. Must be *writeable* by joule user.
  * ``ExporterDataDirectory`` Absolute path to a directory used when processing data exports. Must be *writeable* by joule user.
  * ``ImporterInboxDirectory`` Absolute path to a directory used to process file uploads. Must be *writeable* by joule user. Omit to disable this feature.
  * ``IPAddress`` IP address of interface to listen on. Use **0.0.0.0** to listen on all interfaces.
  * ``Port`` TCP port to listen on
  * ``Database`` PostgreSQL connection information as DSN string.
    Format is **username:password@[domain|ip_address]:port/database**. Database must have TimescaleDB extension
    loaded and initialized.
  * ``InsertPeriod`` how often to send stream data to NilmDB (in seconds)
  * ``CleanupPeriod`` how often to remove old data (in seconds) as specified by stream **keep** parameters
  * ``MaxLogLines`` max number of lines to keep in a module log file (automatically rolls)
  * ``UsersFile`` control access using the specified file (example below), no reload is required.
  * ``[Security]`` This section enables HTTPS using the specified credentials. If this section is omitted
    the server will run with HTTP.
  * ``[Proxies]`` This section lists sites to proxy. This allows access to locally hosted sites through Lumen.

Example Users File Syntax:

.. raw:: html

    <div class="users-file">

      : /etc/joule/users.conf

        # Specify user name and key separated by a ,
        # Keys must be unique and at least 32 characters long
        # If the user exists with a different key, the key is updated.
        # ----------------------------------------------
        # Name, Key
        alice, 044b1a5153e5f736cd787870cc949f2a
        bob, f5b37cd7207ac314a74d57d9c2ff8bb0
        charlie, 126374f04d61ea485883f6fb287defc0

        # Remove users using DELETE, add LIKE for SQL wildcard match (%,_)
        # ----------------------------------------------------------------

        # remove any users with names that begin with temp
        DELETE LIKE temp%

        # remove the user named remote_admin
        DELETE remote_admin


      </div>

.. _sec-configure-docker:

Docker Configuration
--------------------

Joule is available as a Docker container on Docker Hub.  The container tags match the release versions on PyPi, use the latest tag to retrieve the
most recent version of the container.


.. raw:: html

    <div class="bash-code">
    docker pull wattsworth/joule:latest
    </div>

The container can be configured using environment variables
as well as mounted volumes. Configuration variables with their default values
are listed below:

  * ``NODE_NAME`` : ``joule`` name of the node
  * ``POSTGRES_USER`` : ``joule`` PostgreSQL username
  * ``POSTGRES_PASSWORD`` : ``joule`` PostgreSQL password
  * ``POSTGRES_HOST`` : ``postgres`` PostgreSQL host name or IP address
  * ``POSTGRES_PORT`` : ``5432`` PostgreSQL port number
  * ``POSTGRES_DB`` : ``joule`` PostgreSQL database name
  * ``USER_KEY`` : no default value, use a 32 character random string
  * ``HOST_PORT`` : ``80`` Forward facing port when running behind a reverse proxy
  * ``HOST_SCHEME`` : ``http`` Reverse proxy scheme (http or https)

In addition to these environment variables the container can be further customized by mounting the following volumes:

  * ``/etc/joule/configs/users.conf`` : user configuration file, this replaces the ``USER_KEY`` value
  * ``/etc/joule/configs/proxies.conf`` : list of sites to proxy. The format is the same as the main configuration file with one ``<name>=<url>`` pair per line.

For complete control of system configuration mount a volume to ``/etc/joule`` with a ``main.conf`` and files.
This supersedes all other configuration options.

