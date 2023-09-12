.. _cli-reference:

Command Line Interface
----------------------
The command line interface (CLI) can be used to interact with the local Joule service or any Joule node
on the network. Arguments can often be supplied in both short and long forms, and many
are optional. The documentation uses the following conventions:

    * An argument that takes an additional parameter is denoted **-f FILE**.
    * The syntax **-f FILE, --file FILE** indicates that either the short form (-f) or long form (--file) can be used interchangeably.
    * Square brackets ([]) denote optional arguments.
    * Pipes (A|B) indicate that either A or B can be specified, but not both.
    * Curly braces ({}) indicate a list of mutually-exclusive argument choices.

Usage
    joule ~ [--help] [--node|-n] [--version] {subcommand} ...


Arguments
    --node Node: Specify a different node than the default (see ''node list'' for available nodes)
    --help: Print a help message with usage information on all supported command-line arguments. This can also be specified after the subcommand in which case the usage and arguments of the subcommand are shown instead
    --version: print the joule CLI version
    subcommand: The subcommand followed by its arguments. This is required

node
++++

info
''''

show information about the selected node

Usage
    joule node info ~ [--help]
Arguments
    none
Example
    $> joule node info
    --connecting to [XXXX]--
    Server Version:         0.9.XX
    Database Location:      /var/lib/postgresql/12/main
    Database Size:          2GiB
    Space Available:        20GiB

list
''''

add
'''

delete
''''''

default
'''''''

module
++++++


list
''''

list all active modules and pipe connections.

Usage
    joule module list ~ [--help]

Arguments
    none

Example
     $> joule module list
     ╒════════════╤══════════╤═════════════════╤═════════╤═════════════╕
     │ Name       │ Inputs   │ Outputs         │   CPU % │   Mem (KiB) │
     ╞════════════╪══════════╪═════════════════╪═════════╪═════════════╡
     │ Visualizer │          │ /random/output2 │       0 │       59880 │
     ├────────────┼──────────┼─────────────────┼─────────┼─────────────┤
     │ Producer1  │          │ /random/10hertz │       0 │       62644 │
     ├────────────┼──────────┼─────────────────┼─────────┼─────────────┤
     │ Producer2  │          │ /demo/stream1   │       0 │        8028 │
     ╘════════════╧══════════╧═════════════════╧═════════╧═════════════╛

info
''''

information about the specified module

Usage
    joule module info ~ [--help] NAME
Arguments
    NAME: module name (from configuration file)
Example
    .. raw:: html

        $> joule module info Visualizer
        Name:         Visualizer
        Description:  visualizes data
        Inputs:
                --none--
        Outputs:
                output: /random/output2

logs
''''

print module logs

Usage
    joule module logs ~ [--help] NAME

Arguments
    NAME: module name (from configuration file)

Example
    $> joule module logs Visualizer
    [2018-09-11T20:45:58.799616]: ---starting module---
    [2018-09-11T20:45:59.736744]: starting web server at [wattsworth.joule.0]


stream
++++++

list
''''

show the contents of the stream database

Usage
    joule stream list ~ [-l] [-s] [--help]
Arguments
    -l, --layout: include stream layout
    -s, --status: include stream status
Example
    .. raw:: html

        $> joule stream list

        ├── demo
        │   ├── f1
        │   │   └── stream0(1)
        │   ├── copied2(6)
        │   ├── copy one(5)
        │   └── stream1(4)
        └── random
            ├── 10hertz(3)
            ├── output(2)
            └── output2(7)

info
''''

Display information about the specified stream

Usage
    joule stream info ~ [--help] PATH
Arguments
    PATH: stream path
Example
    .. raw:: html

        $> joule stream info /random/10hertz

                Name:         10hertz
                Description:  —
                Datatype:     float32
                Keep:         all data
                Decimate:     yes

                Status:       ● [active]
                Start:        2018-07-25 20:35:49.427396
                End:          2018-09-11 22:11:39.839133
                Rows:         216040

        ╒════════╤═════════╤════════════╤═══════════╕
        │  Name  │  Units  │  Display   │  Min,Max  │
        ╞════════╪═════════╪════════════╪═══════════╡
        │   x    │    —    │ continuous │   auto    │
        ├────────┼─────────┼────────────┼───────────┤
        │   y    │    —    │ continuous │   auto    │
        ├────────┼─────────┼────────────┼───────────┤
        │   z    │    —    │ continuous │   auto    │
        ╘════════╧═════════╧════════════╧═══════════╛

destroy
'''''''

Completely remove the stream at the specified path

Usage
    joule stream destroy ~ PATH
Arguments
    PATH: path of stream to destroy

move
''''

Move a stream into a new folder.

Usage
    joule stream move ~ PATH DESTINATION
Arguments
    PATH: path of stream to move
    DESTINATION: path of destination folder
Notes
    The folder will be created if it does not exist. A stream cannot be moved into
    a folder which has a stream with the same name

folder
++++++

move
''''

move a folder into a new parent folder.

Usage
    joule folder move ~ PATH DESTINATION

Arguments
    PATH: path of folder to move
    DESTINATION: path of new parent folder

Note:
    The parent folder will be created if it does not exist. A folder cannot
    be moved into a parent folder which has a folder with the same name

remove
''''''

remove a folder

Usage
    joule folder remove ~ [-r] PATH

Arguments
    -r, --recursive: remove subfolders
    PATH: path of folder to remove

Notes
    If the folder has subfolders, add ``-r`` to recursively remove them.
    The folder and its subfolders may not have any streams, if they do more or remove them first.

data
++++

copy
''''

copy data between streams

Usage
    joule data copy ~ [-s] [-e] [-n] [-d] [--source-url] SOURCE DESTINATION

Arguments
    -s, --start: timestamp or descriptive string, if omitted start copying at the beginning of SOURCE
    -e, --end: timestamp or descriptive string, if omitted copy to the end of SOURCE
    -n, --new:  copy starts at the last timestamp of the destination
    -d: destination node name or Nilmdb URL if different than source
    --source-url: copy from a Nilmdb URL (specify a Joule node with top level -n flag)

read
''''

extract data from a stream

Usage
    joule data read ~ [-s] [-e] [-r|-d] [-b] [-m] [-i] [-f] PATH

Arguments
    -s, --start: timestamp or descriptive string, if omitted start reading at the beginning
    -e, --end: timestamp or descriptive string, if omitted read to the end
    -r: limit the response to a maximum number of rows (this will produce a decimated result)
    -d: specify a particular decimation level, may not be used with -r, default is 1
    -b: include min/max limits for each row of decimated data
    -m: include [# interval break] tags in the output to indicate broken data intervals
    -f, --file: filename to write data to rather than stdout (written in hdf5 format)
    -i: indices of elements to read, separate multiple elements with ``,`` The first element is index 0

    PATH: path of stream to read

Example
    # write the last hour of data from /demo/random into data.txt
    $> joule data read /demo/random --start="1 hour ago" > data.txt
    $> head data.txt
    1538744825370107 0.383491 0.434531
    1538744825470107 0.317079 0.054972
    1538744825570107 0.572721 0.875278
    1538744825670107 0.350911 0.680056
    1538744825770107 0.839264 0.189361
    1538744825870107 0.259714 0.394411
    1538744825970107 0.027148 0.963998
    1538744826070107 0.828187 0.704508
    1538744826170107 0.738999 0.082351
    1538744826270107 0.828530 0.916019

remove
''''''

remove data from a stream

Usage
    joule data remove ~ [--from] [--to] STREAM

Arguments
    -s, --start: timestamp or descriptive string, if omitted start reading at the beginning of SOURCE
    -e, --end: timestamp or descriptive string, if omitted read to the end of SOURCE

consolidate
'''''''''''

merge data intervals with short gaps

Usage
    joule data consolidate ~ [-s] [-e] [--max-gap] STREAM

Arguments
    -s, --start:     timestamp or descriptive string, if omitted start at the beginning of STREAM
    -e, --end:       timestamp or descriptive string, if omitted run to the end of STREAM
    -m, --max-gap:   remove intervals shorter than this (in us). Default is 2 seconds

admin
+++++

The following commands require super user (sudo) permission and only operate on the
local node. They should only be run when the joule service (jouled) is stopped.

initialize
''''''''''

prepare a system to run the joule service (jouled)

Usage
    joule admin initialize ~ --dsn DSN_STRING

Arguments
    --dsn: connection string to PostgreSQL database

.. _cli-admin-authorize-cmd:

authorize
'''''''''

authorize the current user access to the local node

Usage
    joule admin authorize ~ [-c]

Arguments
    -c, --config: configuration file default is ``/etc/joule/main.conf``

erase
'''''

remove all data from the node

Usage
    joule admin erase ~ [-c] [-l] [--yes]

Arguments
    -c, --config: configuration file default is ``/etc/joule/main.conf``
    -l, --links: remove master/follower relationships, default removes only data
    --yes: force, do not prompt for confirmation

backup
''''''

archive all node data into a single file

Usage
    joule admin backup ~ [-c] [-f]

Arguments
    -c, --config: configuration file default is ``/etc/joule/main.conf``
    -f, --file: backup file name default is ``joule_backup.tar``


ingest
''''''

bulk copy data into the local node

Usage
    joule admin ingest ~ [-c] [-f] [-d|-f] [-m] [-y] [-s] [-e]

Arguments
    -c, --config: configuration file default is ``/etc/joule/main.conf``
    -f, --file: copy data from backup file, default is ``joule_backup.tar``
    -d, --dsn: live copy data from another node, may not be specified with -f
    -m, --map: map file relating source streams to destination streams
    -y, --yes: force, do not prompt for confirmation
    -s, --start: timestamp or descriptive string, if omitted copy from start of source
    -e, --end: timestamp or descriptive string, if omitted copy to the end of source





