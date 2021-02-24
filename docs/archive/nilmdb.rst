
Database
========

Joule uses a NilmDB database instance to store data streams. NilmDB
was developed at MIT by Dr. James Paris. Full documentation is
available in his thesis available at `MIT DSpace
<https://dspace.mit.edu/handle/1721.1/84720>`_. This documentation
covers the command line interface for interacting the the Joule NilmDB
instance.



Data Storage
------------

It is usually a good idea to place the database on a separate disk or
partition to ensure that the system does not run out of disk space due
to excessive NilmDB data. By default the database is located in ``/opt/data``.
This section explains how to properly configure your storage volume.

Primary Drive
+++++++++++++

While this is not recommended you may keep the data on the main root
partition. This is the default and will work without any further
configuration. **Enable data journaling to prevent data corruption
if the system shuts down unexpectedly (eg a power failure)**

To enable data journaling on the root partition use ``tune2fs``. For
example if your root partition is on ``/dev/sda2``:

.. raw:: html

  <div class="header bash">
  Command Line:
  </div>
  <div class="code bash">$> sudo tune2fs -o journal_data /dev/sda2</div>


Secondary drive
++++++++++++++++

The recommended configuration is to store the database to an secondary
drive or at least separate partition. These instructions will show you
how to format and configure a secondary drive for data storage. After
connecting the drive, the first step is to place a usable filesystem
on it. There are many tools that can be used for this but one of the
easiest is GParted. This program must be run as root. From the command
line type type the following:

**Warning!** Be very careful with gparted, formatting the primary drive will destroy the installation


.. raw:: html

  <div class="header bash">
  Command Line:
  </div>
  <div class="code bash"><b>$> sudo gparted</b>
  </div>

Select the extra drive from the dropdown menu as shown. If you are
unsure about the drive name run gparted *without* your drive connected
and see which name is no longer in the list. Tip: if the drive already
has multiple partitions this most likely means it is *not* your secondary
drive and is probably your primary disk.

.. figure:: _static/nilmdb/hdd_gparted_1.png
  :align: center

  Carefully select the device node for the extra drive

.. figure:: _static/nilmdb/hdd_gparted_2.png
  :align: center

  Create a new msdos partition table. This will erase the drive.

Select *Device* > *Create Partition Table* to bring up the Create
Partition dialog. Select ``msdos`` and click Apply. Select
*Partition* > *New* to bring up the New Partition
dialog. Add a new ``ext4`` partition to the drive and assign it the
full extents of the disk (this is the default). Click **Add** to close the
dialog. Finally click **Apply** to format the disk and then close
the program.

.. figure:: _static/nilmdb/hdd_gparted_3.png
  :align: center

  Add an ``ext4`` partition to fill the disk

To use the drive for the database it must be mounted to the correct
location in the filesystem. If the secondary drive is internal you may use the
drive name directly. When using an external drive (connected by USB)
the drive letters cannot be used since they change. The UUID is a
unique drive partition identifier that should be used instead. Determine
the UUID of the storage volume by running the following changing ``sdX1`` to the
correct partition name:

.. raw:: html

  <div class="header bash">
  Command Line:
  </div>
  <div class="code bash"><b>$> blkid /dev/sdX1 </b>
  /dev/sda1: UUID="2b9d3e2e-2520-4a99-9b13-61e67cf470a6" <i># continues...</i>
  </div>

Edit ``/etc/fstab`` and insert one of the following lines depending on the
drive type. Note that you will need to run the word processor as
root (sudo) in order to edit this file.

.. raw:: html

  <div class="header ini">
  /etc/fstab
  </div>
  <div class="code ini"># /etc/fstab: static file system information.
  #
  # &lt;file system&gt; &lt;mount point&gt;   &lt;type&gt;  &lt;options&gt;  &lt;dump&gt;  &lt;pass&gt;
  # ...other entries...
  
  # mount internal drives by name
  /dev/sdX1       /opt/data   ext4    errors=remount-ro,data=journal 0 2
  
  # mount external (USB) drives using UUID for consistent mapping
  UUID=XXXXXX... /opt/data    ext4    errors=remount-ro,data=journal 0 2
  </div>

The final step is to mount the drive and change the permissions so the
nilmdb process can use it. 

.. raw:: html

  <div class="header bash">
  Command Line:
  </div>
  <div class="code bash"><i>#stop data capture if it is already running</i>
  <b>$> sudo service jouled stop</b>
  <b>$> sudo apache2ctl stop</b>

  <i># mount the drive using the fstab entry</i>
  <b>$> sudo mount -a</b>

  <i># assign the drive to the nilmdb user</i>
  <b>$> sudo chown -R nilmdb:nilmdb /opt/data</b>

  <i># output of df should show a mount point at /opt/data:</i>
  <b>$ df -h</b>
  Filesystem      Size  Used Avail Use% Mounted on
  /dev/sdb1       917G   72M  871G   1% /opt/data

  <i># restart joule to begin using the new drive</i>
  <b>$> sudo apache2ctl restart</b>
  <b>$> sudo service jouled restart</b>

  <i># check to make sure the drive is collecting data</i>
  <b>$> nilmtool info</b>
  Client version: 1.10.3
  Server version: 1.10.3
  Server URL: http://localhost/nilmdb/
  ...output continues

  <b>$> nilmtool list -E</b>
  ...check that streams are collecting data
  </div>



Command Line Interface
----------------------

The following are commonly used commands for interacting with 
the NilmDB database. The full list of command line tools are documented
below.

* ``nilmtool list -n`` -- list all streams in the database ignoring decimations
* ``nilmtool list -E /stream/path``-- show the range of data stored in **/stream/path**
* ``nilm-copy /source/path /dest/path`` -- copy data from **/source/path** to **/dest/path**
    DANGER: The following commands remove data, use caution!!

* ``nilmtool remove -s min -e max /stream/path`` -- remove all data form **/stream/path**
* ``nilmtool destroy -R /stream/path`` -- remove **/stream/path** from the database


Command-line arguments can often be supplied in both short and long
forms, and many arguments are optional. The following documentation uses these
conventions:

* An argument that takes an additional parameter is denoted ``-f FILE``.
* The syntax ``-f FILE, --file FILE`` indicates that either the short form (-f) or long form (--file) can be used interchangeably.
* Square brackets (``[]``) denote optional arguments.
* Pipes (``A|B``) indicate that either ``A`` or ``B`` can be specified, but not both.
* Curly braces (``{}``) indicate a list of mutually-exclusive argument choices.

Many of the programs support arguments that represent a NilmDB timestamp. This
timestamp is specified as a free-form string, as supported by the **parse_time**
client library function, described in Section 3.2.2.4 of the NilmDB reference
guide. Examples of accepted formats are shown in Table 3-19 on page 133 of that
document.

``nilmtool``
------------

Tools for interacting with the database are wrapped in ``nilmtool``, a
monolithic multi-purpose program that provides command-line access to most of
the NilmDB functionality. Global operation is described first followed by
specific documentation for each subcommand.

The command-line syntax provides the ability to execute sub- commands: first,
global arguments that affect the behavior of all subcommands can be specified,
followed by one subcommand name, followed by arguments for that subcommand. Each
defines its own arguments and is documented below.

Usage::

  nilmtool [-h] [-v] [-u URL]
           {help,info,create,rename,list,intervals,metadata,insert,extract,remove,destroy}
           ...

Arguments

.. raw:: html

  <div class="block-indent">
    <dl class="arglist">
      <dt>-u URL, --url URL</dt><dd> (default: http://localhost/nilmdb/) NilmDB server URL. Must be specified before the subcommand.</dd>
      <dt>subcommand ...</dt><dd>The subcommand to run, followed by its arguments. This is required.</dd>
      <dt>-h, --help</dt><dd>Print a help message with Usage information and details on all supported command-line arguments. This can also be specified after the subcom- mand, in which case the Usage and arguments of the subcommand are shown instead.</dd>
      <dt>-v, --version</dt><dd>Print the nilmtool version.</dd>
    </dl>
  </div>

Environment Variables:

Some behaviors of nilmtool subcommands can be configured via environment variables.

.. raw:: html

  <div class="block-indent">
    <dl class="arglist">
      <dt>NILMDB_URL</dt><dd> (default: http://localhost/nilmdb/) The default URL of the NilmDB server. This is used if --url is not specified, and can be set as an environment variable to avoid the need to specify it on each invocation of nilmtool.</dd>
      <dt>TZ</dt><dd>(default: system default timezone) The timezone to use when parsing or displaying times. This is usually of the form America/New_York, using the standard TZ names from the IANA
  Time Zone Database</dd>
    </dl>
  </div>

``nilmtool help``
+++++++++++++++++

Print more specific help for a subcommand. nilmtool help subcommand is the same as nilmtool subcommand ``--help``.

Usage::

  nilmtool help [-h] subcommand



``nilmtool info``
+++++++++++++++++
Print server information such as software versions, database location, and disk space Usage.

Usage::

  nilmtool info [-h]

Example

.. code-block:: bash

  $> nilmtool info
  Client version: 1.9.7
  Server version: 1.9.7
  Server URL: http://localhost/nilmdb/
  Server database path: /home/nilmdb/db
  Server disk space used by NilmDB: 143.87 GiB
  Server disk space used by other: 378.93 GiB
  Server disk space reserved: 6.86 GiB
  Server disk space free: 147.17 GiB


``nilmtool create``
+++++++++++++++++++

Create a new empty stream at the specified path and with the specified layout.

Usage::

  nilmtool create [-h] PATH LAYOUT

Arguments

.. raw:: html

  <div class="block-indent">
    <dl class="arglist">
      <dt>PATH</dt><dd>Path of the new stream. DataStream paths are similar to filesystem paths and must contain at least two components. For example, /foo/bar.</dd>
      <dt>LAYOUT</dt><dd>Layout for the new stream. Layouts are of the form &lt;type&gt;_&lt;count&gt;. The &lt;type&gt; is one of those described in Section 2.2.3 of the <a href="#">NilmDB Reference Guide</a>, such as uint16, int64, or float32. &lt;count&gt; is a numeric count of how many data elements there are, per row. Streams store rows of homogeneous data only, and the largest supported &lt;count&gt; is 1024. Generally, counts should fall within a much lower range, typically between 1 and 32. For example, float32_8.</dd>
  </dl>
  </div>


``nilmtool rename``
+++++++++++++++++++

Rename or relocate a stream in the database from one path to another. Metadata and intervals, if any, are relocated to the new path name.

Usage::

  nilmtool rename [-h] OLDPATH NEWPATH

Arguments

.. raw:: html

  <div class="block-indent">
    <dl class="arglist">
      <dt>OLDPATH</dt><dd>Old existing stream path, e.g. /foo/old</dd>
      <dt>NEWPATH</dt><dd>New stream path, e.g. /foo/bar/new</dd>
    </dl>
  </div>

Notes

  Metadata contents are not changed by this operation. Any software tools that
  store and use path names stored in metadata keys or values will need to update
  them accordingly.


``nilmtool list``
+++++++++++++++++

List streams available in the database, optionally filtering by path, and
optionally including extended stream info and intervals.

Usage::

  nilmtool list [-h] [-E] [-d] [-s TIME] [-e TIME] [-T] [-l] [-n]
                     [PATH [PATH ...]]

Arguments

.. raw:: html

  <div class="block-indent">
    <dl class="arglist">
      <dt>PATH</dt><dd>(default: *) If paths are specified, only streams that
      match the given paths are shown. Wildcards are accepted; for example,
      /sharon/* will list all streams with a path beginning with /sharon/.
      Note that, to prevent wildcards from being interpreted by the shell,
      they should be quoted at the command line; for example:
      <pre>
  $> nilmtool list "/sharon/*"
  $> nilmtool list "*raw"</textarea></pre>
      </dd>
      <dt>-E, --ext</dt><dd>Show extended stream information, like interval extents, total rows of data present, and total amount of time covered by the stream’s intervals.</dd>
      <dt>-T, --timestamp-raw</dt><dd>When displaying timestamps in the output, show raw timestamp values from the NilmDB database rather than converting to human-readable times. Raw values are typically measured in microseconds since the Unix time epoch (1970/01/01 00:00 UTC).</dd>
      <dt>-l, --layout</dt><dd>Display the stream layout next to the path name.</dd>
      <dt>-n, --no-decim</dt><dd>Omit streams with paths containing the string ``~decim-``, to avoid cluttering the output with decimated streams.</dd>
      <dt>-d, --detail</dt><dd>In addition to the normal output, show the time intervals present in each stream. See also nilmtool intervals in Section 3.2.3.7 of the <a href="#">NilmDB Reference Guide</a>, which can display more details about the intervals.</dd>
      <dt>-s TIME, --start TIME</dt><dd>Starting timestamp for intervals (free-form, inclusive).</dd>
      <dt>-e TIME, --end TIME</dt><dd>Ending timestamp for intervals (free-form, noninclusive).</dd>
    </dl>
  </div>


``nilmtool intervals``
++++++++++++++++++++++

List intervals in a stream, similar to ``nilmtool list --detail``, but with
options for calculating set-differences between intervals of two streams, and
for optimizing the output by joining adjacent intervals.

Usage::

  nilmtool intervals [-h] [-d PATH] [-s TIME] [-e TIME] [-T] [-o] PATH

Arguments

.. raw:: html

  <div class="block-indent">
    <dl class="arglist">
      <dt>PATH</dt><dd>List intervals for this path.</dd>
      <dt>-d DIFFPATH, --diff DIFFPATH</dt><dd>(default: none) If specified, perform a set-difference by subtract the intervals in this path; that is, only show interval ranges that are present in the original path but not present in diffpath.</dd>
      <dt>-s TIME, --start TIME</dt><dd>Starting timestamp for intervals (free-form, inclusive).</dd>
      <dt>-e TIME, --end TIME</dt><dd>Ending timestamp for intervals (free-form, noninclusive).</dd>
      <dt>-T, --timestamp-raw</dt><dd>(default: min) (default: max) When displaying timestamps in the output, show raw timestamp values from the NilmDB database rather than converting to human-readable times. Raw values are typically measured in microseconds since the Unix time epoch (1970/01/01 00:00 UTC).</dd>
      <dt>-o, --optimize</dt><dd>Optimize the interval output by merging adjacent intervals. For example, the two intervals [1 → 2⟩ and [2 → 5⟩ would be displayed as one interval [1 → 5⟩.</dd>
    </dl>
  </div>


``nilmtool metadata``
+++++++++++++++++++++

Get, set, update, or delete the key/value metadata associated with a stream.

Usage::

  nilmtool metadata path [-g [key ...] | -s key=value [...] | -u key=value [...]] | -d [key ...]

Arguments

.. raw:: html

  <div class="block-indent">
    <dl class="arglist">
      <dt>PATH</dt><dd>Path of the stream for which to manage metadata. Required, and must be specified before the action arguments.</dd>
    </dl>
  </div>

Action Arguments: These actions are mutually exclusive.

.. raw:: html

  <div class="block-indent">
    <dl class="arglist">
      <dt>-g [KEY ...], --get [KEY ...]</dt><dd>(default: all) Get and print metadata for the specified key(s). If none are specified, print metadata for all keys. Keys are printed as key=value, one per line.</dd>
      <dt>-s [KEY=VALUE ...], --set [KEY=VALUE ...]</dt><dd>Set metadata. Keys and values are specified as a key=value string. This replaces all existing metadata on the stream with the provided keys; any keys present in the database but not specified on the command line are removed.</dd>
      <dt>-u [KEY=VALUE ...], --update [KEY=VALUE ...]</dt><dd>Update metadata. Keys and values are specified as a key=value string. This is similar to --set, but only adds or changes metadata keys; keys that are present in the database but not specified on the command line are left unchanged.</dd>
      <dt>-d [KEY ...], --delete [KEY ...]</dt><dd>(default: all) Delete metadata for the specified key(s). If none are specified, delete all metadata for the stream. </dd>
    </dl>
  </div>

Example::

  $> nilmtool metadata /temp/raw --set "location=Honolulu, HI" "source=NOAA"
  $> nilmtool metadata /temp/raw --get
  location=Honolulu, HI
  source=NOAA
  $> nilmtool metadata /temp/raw --update "units=F"
  location=Honolulu, HI
  source=NOAA
  units=F


``nilmtool insert``
+++++++++++++++++++

Insert data into a stream. This is a relatively low-level interface analogous to
the /stream/insert HTTP interface described in Section 3.2.1.13 on the <a
href="#">NilmDB Reference Guide</a>. This is the program that should be used
when a fixed quantity of text-based data is being inserted into a single
interval, with a known start and end time. If the input data does not already
have timestamps, they can be optionally added based on the start time and a
known data rate. In many cases, using the separate ``nilm-insert`` program is
preferable, particularly when dealing with large amounts of pre-recorded data,
or when streaming data from a live source.

Usage::

  nilmtool insert [-h] [-q] [-t] [-r RATE] [-s TIME | -f] [-e TIME]
                       path [file]


Arguments

.. raw:: html

  <div class="block-indent">
    <dl class="arglist">
      <dt>PATH</dt><dd>Path of the stream into which to insert data. The format of the input data must match the layout of the stream.</dd>
      <dt>FILE</dt><dd>(default: standard input) Input data filename, which must be formatted as uncompressed plain text. Default is to read the input from stdin.</dd>
      <dt>-q, --quiet</dt><dd>Suppress printing unnecessary messages.</dd>
    </dl>
  </div>

  <i>Timestamping</i>: To add timestamps to data that does not already have it, specify both of these arguments. The added timestamps are based on the interval start time and the given data rate.
  <div class="block-indent">
    <dl class="arglist">
       <dt>-t, --timestamp</dt><dd>Add timestamps to each line</dd>
       <dt>-r RATE, --rate RATE</dt><dd> Data rate, in Hz</dd>
    </dl>
  </div>
  <i>Start Time</i>: The start time may be manually specified, or it can be determined from the input filename, based on the following options.
  <div class="block-indent">
    <dl class="arglist">
      <dt>-s TIME, --start TIME</dt><dd>Starting timestamp for the new interval (free-form, inclusive)</dd>
      <dt>-f, --filename</dt><dd>Use filename to determine start time</dd>
    </dl>
  </div>
  <i>End Time</i>: The ending time should be manually specified. If timestamps are being added, this can be omitted, in which case the end of the interval is set to the last timestamp plus one microsecond.
  <div class="block-indent">
    <dl class="arglist">
      <dt>-e TIME, --end TIME</dt><dd>Ending timestamp for the new interval (free-form, noninclusive)</dd>
    </dl>
  </div>

``nilmtool extract``
++++++++++++++++++++

Extract rows of data from a specified time interval in a stream, or output a
count of how many rows are present in the interval.

Usage::

  nilmtool extract [-h] -s TIME -e TIME [-B] [-b] [-a] [-m] [-T] [-c]
                        path


Arguments

.. raw:: html

  <div class="block-indent">
    <dl class="arglist">
      <dt>PATH</dt><dd>Path of the stream from which to extract data.</dd>
      <dt>-s TIME, --start TIME</dt><dd>Starting timestamp to extract (free-form, inclusive)</dd>
      <dt>-e TIME, --end TIME</dt><dd>Ending timestamp to extract (free-form, noninclusive)</dd>
    </dl>
  </div>
  <i>Output Formatting</i>
  <div class="block-indent">
    <dl class="arglist">
      <dt>-B, --binary</dt><dd>Output raw binary data instead of the usual text format. For details on the text and binary formatting, see the documentation of HTTP call /stream/insert in Section 3.2.1.13.</dd>
      <dt>-b, --bare</dt><dd>Omit timestamps from each line of the output.</dd>
      <dt>-a, --annotate</dt><dd>Include comments at the beginning of the output with information about the stream. Comments are lines beginning with #.</dd>
      <dt>-m, --markup</dt><dd>Include comments in the output with information that denotes where the stream’s internal intervals begin and end. See the documentation of the markup parameter to HTTP call /stream/extract in Section 3.2.1.14 for details on the format of the comments.</dd>
      <dt>-T, --timestamp-raw</dt><dd>Use raw integer timestamps in the --annotate output instead of human- readable strings.</dd>
      <dt>-c, --count</dt><dd>Instead of outputting the data, output a count of how many rows are present in the given time interval. This is fast as it does not transfer the data from the server.</dd>
    </dl>
  </div>


``nilmtool remove``
+++++++++++++++++++

Remove all data from a specified time range within the stream at /PATH/.
Multiple streams may be specified, and wildcards are supported; the same time
range will be removed from all matching streams.

Usage::

  nilmtool remove [-h] -s TIME -e TIME [-q] [-c] path [path ...]

Arguments

.. raw:: html

  <div class="block-indent">
    <dl class="arglist">
      <dt>PATH</dt><dd> Path(s) of streams. Wildcards are supported. At least one path must provided.</dd>
      <dt>-s TIME, --start TIME</dt><dd>Starting timestamp of data to remove (free-form, inclusive, required).</dd>
      <dt>-e TIME, --end TIME</dt><dd>Ending timestamp of data to remove (free-form, noninclusive, required).</dd>
    </dl>
  </div>
  <i>Output Format</i>
  <div class="block-indent">
    <dl class="arglist">
      <dt>-q, --quiet</dt><dd>By default, matching path names are printed when removing from multiple paths. With this option, path names are not printed.</dd>
      <dt>-c, --count</dt><dd>Display a count of the number of rows of data that were removed from each path.</dd>
    </dl>
  </div>

Example::

  $ nilmtool remove -s @1364140671600000 -e @1364141576585000 -c "/sh/raw*"
  Removing from /sh/raw
  7239364
  Removing from /sh/raw~decim-4
  1809841
  Removing from /sh/raw~decim-16
  452460


``nilmtool destroy``
++++++++++++++++++++

Destroy the stream at the specified path(s); the opposite of nilmtool create.
Metadata related to the stream is permanently deleted. All data must be removed
before a stream can be destroyed. Wildcards are supported.

Usage::

  nilmtool destroy [-h] [-R] [-q] path [path ...]

Arguments

.. raw:: html

  <div class="block-indent" style="padding-bottom: 30px">
    <dl class="arglist">
      <dt>PATH</dt><dd>Path(s) of streams. Wildcards are supported. At least one path must provided.</dd>
      <dt>-R, --remove</dt><dd>If specified, all data is removed before destroying the stream. Equivalent to first running <span class="mono">nilmtool remove -s min -e max path``.</dd>
      <dt>-q, --quiet</dt><dd>Don’t display names when destroying multiple paths</dd>
    </dl>
  </div>

``nilm-copy``
-------------

Copy data and metadata from one stream to another. The source and destination
streams can reside on different servers. Both streams must have the same layout.
Only regions of time that are present in the source, and not yet present in the
destination, are processed. This program can therefore be re-run with the same
command-line arguments multiple times, and it will only process the newly
available data each time.

Usage::

  nilm-copy [-h] [-v] [-u URL] [-U DEST_URL] [-D] [-F] [-s TIME]
                 [-e TIME] [-n] [-x]
                 srcpath destpath

Arguments

.. raw:: html

  <div class="block-indent">
    <dl class="arglist">
      <dt>-u URL, --url URL</dt><dd> (default: http://localhost/nilmdb/) NilmDB server URL for the source stream.</dd>
      <dt>-U DESTURL, --dest-url DESTURL</dt><dd> (default: same as URL) NilmDB server URL for the destination stream. If unspecified, the same URL is used for both source and destination.</dd>
      <dt>-D, --dry-run</dt><dd>Just print intervals that would be processed, and exit.</dd>
      <dt>-F, --force-metadata</dt><dd>Metadata is copied from the source to the destination. By default, an error is returned if the destination stream metadata conflicts with the source stream metadata. Specify this flag to always overwrite the destination values with those from the source stream.</dd>
      <dt>-n, --nometa</dt><dd>Don’t copy or check metadata at all.</dd>
      <dt>-s TIME, --start TIME</dt><dd>(default: min) Starting timestamp of data to copy (free-form, inclusive).</dd>
      <dt>-e TIME, --end TIME</dt><dd>(default: max) Ending timestamp of data to copy (free-form, noninclusive).</dd>
      <dt>SRCPATH</dt><dd>Path of the source stream (on the source server).</dd>
      <dt>DESTPATH</dt><dd>Path of the destination stream (on the destination server).</dd>
    </dl>
  </div>



``nilm-copy-wildcard``
----------------------

Copy data and metadata, from multiple streams, between two servers. Similar to nilm-copy, except:

* Wildcards and multiple paths are supported in the stream names.
* Streams must always be copied between two servers.
* DataStream paths must match on the source and destination server.
* If a stream does not exist on the destination server, it is created with the correct layout automatically.


Usage::

  nilm-copy-wildcard [-h] [-v] [-u URL] [-U DEST_URL] [-D] [-F] [-s TIME]
                          [-e TIME] [-n] [-x]
                          path [path ...]

Arguments

.. raw:: html

  <div class="block-indent">
  Most arguments are identical to those of nilm-copy (reference it for more details).
  <dl class="arglist">
    <dt>PATHS</dt><dd>Path(s) to copy from the source server to the destination server. Wildcards are accepted.</dd>
  </dl>
  </div>

Example::

  $ nilm-copy-wildcard -u http://bucket/nilmdb -U http://pilot/nilmdb /bp/startup*
   Source URL: http://bucket/nilmdb/
   Dest URL: http://pilot/nilmdb/
  Creating destination stream /bp/startup/info
  Creating destination stream /bp/startup/prep-a
  Creating destination stream /bp/startup/prep-a~decim-4
  Creating destination stream /bp/startup/prep-a~decim-16
  # ... etc


``nilm-decimate``
-----------------

Decimate the stream at SRCPATH and write the output to DESTPATH. The
decimation operation is described in Section 2.4.1; in short, every FACTOR rows
in the source are consolidated into one row in the destination, by calculating
the mean, minimum, and maximum values for each column. This program
detects if the stream at SRCPATH is already decimated, by the presence of a
decimate_source metadata key. If present, subsequent decimations take the
existing mean, minimum, and maximum values into account, and the output has the
same number of columns as the input. Otherwise, for the first level of
decimation, the output has three times as many columns as the input. See
also nilm-decimate-auto (Section 3.4.2.5) for a simpler method of decimating a
stream by multiple levels.

Usage::

  nilm-decimate [-h] [-v] [-u URL] [-U DEST_URL] [-D] [-F] [-s TIME]
                     [-e TIME] [-n] [-f FACTOR]
                     srcpath destpath

Arguments

.. raw:: html

  <div class="block-indent">
    <dl class="arglist">
      <dt>-u URL, --url URL</dt><dd>(default: http://localhost/nilmdb/) NilmDB server URL for the source stream.</dd>
      <dt>-U DESTURL, --dest-url DESTURL</dt><dd>(default: same as URL) NilmDB server URL for the destination stream. If unspecified, the same URL is used for both source and destination.</dd>
      <dt>-D, --dry-run</dt><dd>Just print intervals that would be processed, and exit.</dd>
      <dt>-F, --force-metadata</dt><dd>Overwrite destination metadata even if it conflicts with the values in the “metadata” section below.</dd>
      <dt>-s TIME, --start TIME</dt><dd>(default: min) Starting timestamp of data to decimate (free-form, inclusive).</dd>
      <dt>-e TIME, --end TIME</dt><dd>(default: max) Ending timestamp of data to decimate (free-form, noninclusive).</dd>
      <dt>-f FACTOR, --factor FACTOR</dt><dd>(default: 4) Set the decimation factor. For a source stream with n rows, the output stream will have n/FACTOR rows.</dd>
      <dt>SRCPATH</dt><dd>Path of the source stream (on the source server).</dd>
      <dt>DESTPATH</dt><dd>Path of the destination stream (on the destination server).</dd>
    </dl>
  </div>

The destination stream has the following metadata keys added:

decimate_source
  The source stream from which this data was decimated.
decimate_factor
  The decimation factor used.


``nilm-decimate-auto``
----------------------

Automatically create multiple decimation levels using from a single source
stream, continuing until the last decimated level contains fewer than 500 rows
total. Decimations are performed using nilm-decimate (Section 3.4.2.4).
Wildcards and multiple paths are accepted. Output streams are automatically
named based on the source stream name and the total decimation factor; for
example, ``/test/raw~decim-4``, ``/test/raw~decim-16``, etc. Streams containing
the string "``~decim-``" are ignored when matching wildcards.

Usage::

  nilm-decimate-auto [-h] [-v] [-u URL] [-f FACTOR] [-F] [--fast]
                          path [path ...]

Arguments

.. raw:: html

  <div class="block-indent">
    <dl class="arglist">
      <dt>-u URL, --url URL</dt><dd> (default: http://localhost/nilmdb/) NilmDB server URL for the source and destination streams.</dd>
      <dt>-F, --force-metadata</dt><dd>Overwrite destination metadata even if it conflicts with the values in the “metadata” section above.</dd>
      <dt>-f FACTOR, --factor FACTOR</dt><dd>(default: 4) Set the decimation factor. Each decimation level will have 1/FACTOR as many rows as the previous level.</dd>
      <dt>PATH [...]</dt><dd>One or more paths to decimate. Wildcards are accepted.</dd>
    </dl>
  </div>



``nilm-insert``
---------------

Insert a large amount of text-formatted data from an external source like
ethstream. This is a higher-level tool than nilmtool insert in that it attempts
to intelligently manage timestamps. The general concept is that it tracks two
timestamps:

1. The data timestamp is the precise timestamp corresponding to a particular row of data, and is the timestamp that gets inserted into the database. It increases by data_delta for every row of input. data_delta can come from one of two sources. If --delta is specified, it is pulled from the first column of data. If --rate is specified, data_delta is set to a fixed value of 1/RATE.
2.  The clock timestamp is the less precise timestamp that gives the absolute time. It can come from two sources. If --live is specified, it is pulled directly from the system clock. If --file is specified, it is extracted from the input file every time a new file is opened for read, and from comments that appear in the files.

Small discrepancies between data and clock are ignored. If the data timestamp ever differs from the clock timestamp by more than max_gap seconds:

* If data is running behind, there is a gap in the data, so the timestamp is stepped forward to match clock.
* If data is running ahead, there is overlap in the data, and an error is returned. If --skip is specified, then instead of returning an error, data is dropped and the remainder of the current file is skipped.

Usage::

  nilm-insert [-h] [-v] [-u URL] [-D] [-s] [-m SEC] [-r RATE | -d]
                   [-l | -f] [-o SEC] [-O SEC]
                   path [infile [infile ...]]

Arguments

.. raw:: html

  <div class="block-indent">
    <dl class="arglist">
      <dt>-u URL, --url URL</dt><dd> (default: http://localhost/nilmdb/) NilmDB server URL.</dd>
      <dt>-D, --dry-run</dt><dd>Parse files and print information, but don’t insert any data. Useful for verification before making changes to the database.</dd>
      <dt>-s, --skip</dt><dd>Skip the remainder of input files if the data timestamp runs too far ahead of the clock timestamp. Useful when inserting a large directory of existing files with inaccurate timestamps.</dd>
      <dt>-m SEC, --max-gap SEC</dt><dd>(default: 10.0) Maximum discrepancy between the clock and data timestamps.</dd>
    </dl>
  </div>

  <i>Data timestamp</i>
  <div class="block-indent">
    <dl class="arglist">
      <dt>-r RATE, --rate RATE</dt><dd>(default: 8000.0) data_delta is constant 1/RATE (in Hz).</dd>
      <dt>-d, --delta</dt><dd>data_delta is provided as the first number on each input line.</dd>
    </dl>
  </div>
  <i>Clock timestamp</i>
  <div class="block-indent">
    <dl class="arglist">
      <dt>-l, --live</dt><dd>Use the live system time for the clock timestamp. This is most useful when piping in data live from a capture device.</dd>
      <dt>-f, --file</dt><dd>Use filename and file comments for the clock timestamp. This is most useful when reading previously saved data.</dd>
      <dt>-o SEC, --offset-filename SEC</dt><dd>(default: −3600.0) Offset to add to timestamps in filenames, when using --file. The default accounts for the existing practice of naming capture files based on the end of the hour in which they were recorded. The filename timestamp plus this offset should equal the time that the first row of data in the file was captured.</dd>
      <dt>-O SEC, --offset-comment SEC</dt><dd>(default: 0.0) Offset to add to timestamps in comments, when using --file. The comment timestamp plus this offset should equal the time that the next row of data was captured.</dd>
    </dl>
  </div>
  <i>Path and Input</i>
  <div class="block-indent">
    <dl class="arglist">
      <dt>PATH</dt><dd>Path of the stream into which to insert data. The layout of the path must match the input data.</dd>
      <dt>INFILE [...]</dt><dd>(default: standard input) Input data filename(s). Filenames ending with .gz are transparently decompressed as they are read. The default is to read the input from stdin.</dd>
    </dl>
  </div>

.. DANGER::

    The following tools provide low level access to the NILM and are not
    required for normal system use. Be careful running them as they may
    corrupt the database or cause loss of data.

``nilmdb-server``
-----------------

Run a standalone NilmDB server. Note that the NilmDB server is typically run
as a WSGI process managed by Apache. This program runs NilmDB
using a built-in web server instead.

Usage::

  nilmdb-server [-h] [-v] [-a ADDRESS] [-p PORT] [-d DATABASE] [-q] [-t]
                     [-y]

Arguments

.. raw:: html

  <div class="block-indent">
    <dl class="arglist">
      <dt>-v, --version</dt><dd> Print the installed NilmDB version.</dd>
      <dt>-a ADDRESS, --address ADDRESS</dt><dd> (default: 0.0.0.0) Only listen on the given IP address. The default is to listen on all addresses.</dd>
      <dt>-p PORT, --port PORT</dt><dd>(default: 12380) Listen on the given TCP port.</dd>
      <dt>-d DATABASE, --database DATABASE</dt><dd>(default: ./db) Local filesystem directory of the NilmDB database.</dd>
      <dt>-q, --quiet</dt><dd>Silence output.</dd>
    </dl>
  </div>
  <i>Debug Options</i>
  <div class="block-indent">
    <dl class="arglist">
      <dt>-t, --traceback</dt><dd>Provide tracebacks in the error response for client errors (HTTP status codes 400 - 499). Normally, tracebacks are only provided for server errors (HTTP status codes 500 - 599).</dd>
      <dt>-y, --yappi</dt><dd>Run under the yappi profiler and invoke an interactive shell afterwards. Not intended for normal operation.</dd>
    </dl>
  </div>

``nilmdb-fsck``
---------------

Check database consistency, and optionally repair errors automatically, when
possible. Running this may be necessary after an improper shutdown or other
corruption has occurred. This program will refuse to run if the database is
currently locked by any other process, like the Apache webserver; such programs
should be stopped first. This is run automatically on system boot for the Joule
database.

Usage::

  nilmdb-fsck [-h] [-v] [-f] [-n] database

Arguments

.. raw:: html

  <div class="block-indent">
    <dl class="arglist">
      <dt>DATABASE</dt><dd>Local filesystem directory of the NilmDB database to check.</dd>
      <dt>-f, --fix</dt><dd>Attempt to fix errors when possible. Note that this may involve removing intervals or data.</dd>
      <dt>-n, --no-data</dt><dd>Skip the slow full-data check. The earlier, faster checks are likely to find most database corruption, so the data checks may be unnecessary.</dd>
      <dt>-h, --help</dt><dd>Print a help message with Usage information and details.</dd>
      <dt>-v, --version</dt><dd>Print the installed NilmDB version. Generally, you should ensure that the version of nilmdb-fsck is newer than the NilmDB version that created, or last used, the given database.</dd>
    </dl>
  </div>


``nilm-cleanup``
----------------

Clean up old data from streams, using a configuration file to specify which data
to remove. The configuration file is a text file in the following format::

  [/stream/path]
  keep = 3w # keep up to 3 weeks of data
  rate = 8000 # optional, used for the --estimate option
  decimated = false # whether to delete decimated data too
  [*/wildcard/path]
  keep = 3.5m # or 2520h or 105d or 15w or 0.29y

DataStream paths are specified inside square brackets (``[]``) and are followed by configuration
keywords for the matching streams. Paths can contain wildcards. Supported keywords are:

``keep``
  How much data to keep. Supported suffixes are h for hours, d for days, w for weeks, m for months, and y for years.
``rate``
  (default: automatic) Expected data rate. Only used by the ``--estimate option``. If not specified, the rate is guessed based on the existing data in the stream.
``decimated``
  (default: true) If true, delete decimated data too. For stream path /A/B, this includes any stream matching the wildcard /A/B~decim*. If specified as false, no special treatment is applied to such streams.

The value keep is a maximum amount of data, not a cutoff time. When cleaning
data, the oldest data in the stream will be removed, until the total remaining
amount of data is less than or equal to keep. This means that data older than
keep will remain if insufficient newer data is present; for example, if new data
ceases to be inserted, old data will cease to be deleted.

Usage::

  nilm-cleanup [-h] [-v] [-u URL] [-y] [-e] configfile

Arguments

.. raw:: html
	 
  <div class="block-indent">
    <dl class="arglist">
      <dt>-u URL, --url URL</dt><dd> (default: http://localhost/nilmdb/) NilmDB server URL.</dd>
      <dt>-y, --yes</dt><dd>Actually remove the data. By default, nilm-cleanup only prints what it would have removed, but leaves the data intact.</dd>
      <dt>-e, --estimate</dt><dd>Instead of removing data, print an estimated report of the maximum amount of disk space that will be used by the cleaned-up streams. This uses the on-disk size of the stream layout, the estimated data rate, and the space required by decimation levels. Streams not matched in the con- figuration file are not included in the total.</dd>
      <dt>CONFIGFILE</dt><dd> Path to the configuration file. </dd>
    </dl>
  </div>
