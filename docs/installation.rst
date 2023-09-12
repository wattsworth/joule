.. _installation:

============
Installation
============

This guide provides instructions for installing one or more components of the Wattsworth stack. The choice of
components and their configuration depends on your use case. If you are unsure of which components you need simply follow
this guide in order starting with the :ref:`sec-install-prereqs` section below.

* **Standalone System**:  :ref:`sec-install-joule` and :ref:`sec-install-lumen` with :ref:`sec-install-nginx`:

* **Data Acquisition Node**: :ref:`sec-install-joule` with :ref:`sec-install-nginx`
* **Data Analysis Node**: :ref:`sec-install-joule` in a virtual environment
* **Data Access Node**: :ref:`sec-install-lumen` with :ref:`sec-install-nginx`

.. _sec-install-prereqs:

Prerequistes
============

.. _sec-install-docker:

Docker
------

Install the Docker using the instructions for your OS available on https://docs.docker.com/engine/install/. The script
below should work on most OS distributions but is not generally recommend for production systems.

.. raw:: html

  <div class="bash-code">
  curl -sSL https://get.docker.com | sh
  </div>


.. _sec-install-timescaledb:

TimescaleDB
-----------
Joule stores data in a TimescaleDB database. Create the files below and then run the following commands to install TimescaleDB
in a :ref:`sec-install-docker` container. The first file is a docker-compose file that will create a docker container running TimescaleDB. The second file is a systemd service file that
automatically starts the container when the system boots.  If you already have a TimescaleDB instance you can skip this step.
If you plan to use this system in production consider changing the ``POSTGRES_PASSWORD`` environment variable to a more secure value.

.. raw:: html

  <div class='header ini'>
  /opt/timescaledb/docker-compose.yml
  </div>
  <div class="hjs-code"><pre><code class="language-yaml">version: "3.9"

  services:
    postgres:
      image: timescale/timescaledb:2.11.2-pg15
      restart: always
      environment:
        POSTGRES_USER: joule
        POSTGRES_PASSWORD: joule
        POSTGRES_DB: joule
      volumes:
        - /opt/timescaledb/data:/var/lib/postgresql/data  # persist data
      ports:
        - 127.0.0.1:5432:5432</code></pre></div>

.. raw:: html

    <div class="header ini">
    /etc/systemd/system/timescaledb.service
    </div>
    <div class="hjs-code"><pre><code class="language-ini">[Unit]
    Description=TimescaleDB
    After=docker.service

    [Service]
    Type=simple
    WorkingDirectory=/opt/timescaledb
    ExecStart=/usr/bin/docker compose up
    ExecStop=/usr/bin/docker compose down
    Restart=always
    RestartSec=10

    [Install]
    WantedBy=multi-user.target</code></pre></div>

After creating the files above, run the following commands to start the TimescaleDB container and configure it to start on system boot.

.. raw:: html

    <div class="bash-code">
    sudo systemctl enable timescaledb.service
    sudo systemctl start timescaledb.service

    # track container installation progress (Ctrl-C to exit)
    sudo journalctl -u timescaledb.service -f
    </div>

Wait until you see a log message similar to the following before continuing:

 ``timescaledb-postgres-1  | LOG:  database system is ready to accept connections``

.. _sec-install-joule:

Joule
=====
The ``jouled`` daemon requires a Linux OS while the ``joule`` client can be used on any OS.
Both are contained in the *joule* pypi package and require Python 3.9 or later.
Omit the second command if you plan on using the client functionality only.

.. raw:: html

    <div class="bash-code">
    sudo pip3 install joule
    sudo joule admin initialize --dsn joule:joule@localhost:5432/joule
    </div>

These commands do the following:

1. Install ``joule`` using pip. This will install the package into the system python environment which is the recommended configuration for data acquisition. You may use a virtual environment if you prefer but you will need to modify the service file and other instructions to point to the correct location of the *jouled* and *joule* executables.

2. Initialize Joule with database connection information. If you are using the :ref:`sec-install-timescaledb` docker container configuration above, use the connection string shown. Otherwise modify it to match your database configuration and credentials. The DSN format is:``<username>:<password>@<host>:<port>/<database>``

.. _sec-install-lumen:

Lumen
=====

Lumen provides a web frontend to visualize and interact with data collected by Joule nodes. The following instructions
configure Lumen in a :ref:`sec-install-docker` container which is suitable to run on any host OS. The container is configured with environment
variables specified in the ``.env`` file. Documentation on the particular settings is contained in the sample environment
file and can be used as is in most situations although changing the ``SECRET_KEY_BASE`` is recommended.

.. raw:: html

    <div class="bash-code">
    sudo mkdir /opt/lumen && cd /opt/lumen
    sudo curl -sL https://raw.githubusercontent.com/wattsworth/lumen-docker/main/docker-compose.yml -o docker-compose.yml
    sudo curl -sL https://raw.githubusercontent.com/wattsworth/lumen-docker/main/sample.env -o .env
    </div>

Create the service file below and then run the following commands to configure Lumen to start on system boot.

.. raw:: html

    <div class="header ini">
    /etc/systemd/system/lumen.service
    </div>
    <div class="hjs-code"><pre><code class="language-ini">[Unit]
    Description=Lumen
    After=docker.service

    [Service]
    Type=simple
    WorkingDirectory=/opt/lumen
    ExecStart=/usr/bin/docker compose up
    ExecStop=/usr/bin/docker compose down
    Restart=always
    RestartSec=10

    [Install]
    WantedBy=multi-user.target</code></pre></div>

.. raw:: html

        <div class="bash-code">
        sudo systemctl enable lumen.service
        sudo systemctl start lumen.service

        # track container installation progress (Ctrl-C to exit)
        sudo journalctl -u lumen.service -f
        </div>

The initial set up for this container can take several minutes.
Wait until you see a log message similar to the following which indicates the
web application is running before continuing:

 ``lumen-lumen-1 | [...omitted...]: Passenger core online, PID 54``

.. _sec-install-nginx:

Nginx
=====

Nginx is a reverse proxy webserver that is used to provide external access to both Lumen and Joule. The following commands
install Nginx, remove the default site and install the configuration files for Lumen and Joule. These files are referenced
in the site configuration file. If only using Lumen, you may omit the Joule configuration file and vice versa. The ``adduser``
command grants Nginx access to the Joule socket file, it is only needed if running Joule.

.. raw:: html

    <div class="bash-code">
    sudo apt-get install nginx -y
    sudo rm /etc/nginx/sites-enabled/default

    # install Lumen configuration files
    sudo curl -sL https://raw.githubusercontent.com/wattsworth/lumen-docker/main/host/wattsworth-maps.conf -o /etc/nginx/conf.d/wattsworth-maps.conf
    sudo curl -sL https://raw.githubusercontent.com/wattsworth/lumen-docker/main/host/lumen.conf -o /etc/nginx/lumen.conf
    sudo curl -sL https://raw.githubusercontent.com/wattsworth/lumen-docker/main/host/joule.conf -o /etc/nginx/joule.conf

    # grant Nginx access to Joule, omit if only using Lumen
    sudo adduser www-data joule
    </div>

Select one of the configuration files below and modify the ``server_name`` to match your domain. No additional configuration
is required to host an HTTP site.

.. raw:: html

    <div class="header ini">
    <b>HTTP</b> /etc/nginx/sites-enabled/wattsworth.conf
    </div>
    <div class="hjs-code"><pre><code>server{
	listen 80;

	# server_name directive is optional, but recommended

	# Include one or both statements below to enable lumen and/or joule
	include "/etc/nginx/lumen.conf";
	include "/etc/nginx/joule.conf";
    }</code></pre></div>

To host the site on HTTPS, you will need a valid SSL certificate and
modify the configuration file to include the certificate and key files. If Lumen is configured to host applications on
subdomains (see documentation in ``/opt/lumen/.env``), you will need a CNAME DNS record mapping ``*.app.<yourdomain>`` to ``<yourdomain>``
and for HTTPS you will need a wildcard certificate for ``*.app.<yourdomain>``.

.. raw:: html

    <div class="header ini">
    <b>HTTPS</b> /etc/nginx/sites-enabled/wattsworth.conf
    </div>
    <div class="hjs-code"><pre><code># Note this requires a valid SSL certificate that matches the servername
    # Subdomain applications require a wildcard certificate for *.app.&lt;domain&gt;
    server{
        listen 80; # redirect http traffic to https
        return 301 https://$host$request_uri;
    }

    server{
        listen 443 ssl;
        # Change server name to match your domain
        # include *.app if using subdomain apps configuration
        server_name example.wattsworth.net *.app.example.wattsworth.net;

        # Include one or both statements below to enable lumen and/or joule
        include "/etc/nginx/lumen.conf";
        include "/etc/nginx/joule.conf";

        # Security configuration
        # Note: For subdomain apps this must include wildcard *.app.<yourdomain>
        ssl_certificate fullchain.pem;
        ssl_certificate_key privkey.pem;
    }</code></pre></div>

Finally, restart Nginx to reflect the new configuration:

.. raw:: html

    <div class="bash-code">
    sudo systemctl restart nginx
    </div>

Continue to :ref:`quick-start` to start using Wattsworth.