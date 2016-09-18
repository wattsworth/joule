"""
Database interface to hold information
about the joule daemon and its processes
"""
import nilmdb.client.numpyclient as numpyclient
import nilmtools.filter
import sqlite3
from . import models
import os
import contextlib
from joule.daemon import inputmodule

NILMDB_URL = "http://localhost/nilmdb"
PROC_DB = "/tmp/joule-proc-db.sqlite"

def register_input_module(input_module):
    """add an InputModule to the proc database"""
    dest = input_module.destination
    #1.) create a new path or ensure that
    #    the existing path matches input_module's datatype
    _create_destination_path(dest)
    #2.) check if any other modules are using this path
    other_module = _get_module_by_dest_path(dest.path)
    if(other_module):
        raise ConfigError("the path [%s] is being used by module [%s]"%
                          (dest.path,other_module.name))
    #3.) all good, register the module
    db_module = models.DbInputModule(input_module.name,
                                     dest.path,
                                     inputmodule.STATUS_LOADED)
    _insert_db_input_module(db_module)


def input_modules():
    """returns an array of all the DbInputModule objects"""
    pass

@contextlib.contextmanager
def _procdb_cursor():
    """opens the procdb sqlite database (creates it if needed)"""
    if (not os.path.isfile(PROC_DB)):
        _initialize_procdb()
    conn = sqlite3.connect(PROC_DB)
    c = conn.cursor()
    yield c
    conn.commit()
    conn.close()

def _initialize_procdb():
    """create the procdb sqlite database"""
    conn = sqlite3.connect(PROC_DB)
    c = conn.cursor()
    for table in models.schema:
        c.execute('CREATE TABLE {tn} (id INTEGER PRIMARY KEY)' .format(tn=table['name']))
        for column in table['columns']:
            c.execute("ALTER TABLE {tn} ADD COLUMN '{cn}' {ct}"
                      .format(tn=table["name"],cn=column[0],ct=column[1]))
    conn.commit()
    conn.close()

def _create_destination_path(destination):
    client = _get_numpy_client()
    info = nilmtools.filter.get_stream_info(client,destination.path)
    if info:
        #path exists, make sure the structure matches what this destination wants
        if(info.layout_type != destination.datatype):
            raise ConfigError("the path [%s] has datatype [%s], but the module uses [%s]"%
                              (destination.path,info.layout_type,destination.datatype))
        if(info.layout != destination.data_format):
            raise ConfigError("the path[%s] has [%d] streams, but the module uses [%d]"%
                              (destination.path, info.layout_count, len(destination.streams)))
        #datatype and stream count match so we are ok
    else:
        client.stream_create(destination.path,"%s_%d"%
                             (destination.datatype,len(destination.streams)))

def _get_module_by_dest_path(path):
    with _procdb_cursor() as c:
        c.execute("SELECT * FROM DbInputModules WHERE destination_path ='{path}'".
                  format(path=path))
        module_tuple = c.fetchone()
    if module_tuple is None:
        return None
    #slice off the id field and create a DbInputModule object to return
    return(models.DbInputModule(*module_tuple[1:]))

def _insert_db_input_module(db_input_module):
    with _procdb_cursor() as c:
        #use string substitution to escape db_input_module insert
        c.execute("INSERT INTO DbInputModules VALUES (%s)"%','.
                  join(['?' for x in range(len(models.DbInputModule._fields)+1)]),
                  (None,*db_input_module))
                  
def _get_numpy_client():
    return numpyclient.NumpyClient(NILMDB_URL)

class ProcDbError(Exception):
    """Base class for exceptions in this module"""

class ConfigError(ProcDbError):
    """Error caused by user misconfiguration"""
