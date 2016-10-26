"""
Database interface to hold information
about the joule daemon and its processes
"""
import nilmdb.client.numpyclient as numpyclient
import nilmtools.filter
import sqlite3
from . import schema
import os
import time
import contextlib
from joule.daemon import inputmodule

NILMDB_URL = "http://localhost/nilmdb"
PROC_DB = "/tmp/joule-proc-db.sqlite"

def register_input_module(input_module,config_file=""):
    """add an InputModule to the proc database"""
    dest = input_module.destination
    #1.) create a new path or ensure that
    #    the existing path matches input_module's datatype
    _create_destination_path(dest)
    #2.) check if any other modules are using this path
    other_module = _get_module_by_column("destination_path",dest.path)
    if(other_module):
        raise ConfigError("the path [%s] is being used by module [%s]"%
                          (dest.path,other_module.name))
    #3.) all good, register the module
    _insert_module(input_module,config_file)

def clear_input_modules():
    """remove all registered input modules"""
    with _procdb_cursor() as c:
        #use string substitution to escape db_input_module insert
        c.execute("DELETE FROM {table}".format(table=schema.modules['table']))

def update_module(module):
    with _procdb_cursor() as c:
        #these are the update-able fields in the module structure
        data = {'pid': module.pid,
                'status': module.status
        }
        fields = ",".join(["%s=?"%name for name in data.keys()])
        c.execute("UPDATE {table} SET {fields} WHERE id = ?".
                  format(table = schema.modules['table'],
                         fields = fields),(*data.values(),module.id))

def find_module_by_name(module_name):
    return _get_module_by_column("name",module_name)

def find_module_by_id(module_id):
    return _get_module_by_column("id",module_id)

def find_module_by_dest_path(path):
    return _get_module_by_column("destination_path",path)

def log_to_module(line,module_id):
    """add a log line to the database associated with module_id"""
    with _procdb_cursor() as c:
        data = [None,line,module_id,int(time.time())]
        c.execute("INSERT INTO {table} VALUES (?,?,?,?)".format(table=schema.logs["table"]),
                  data)

def input_modules():
    modules = []
    with _procdb_cursor() as c:
        c.execute("SELECT * FROM {table}".format(table=schema.modules['table']))
        for row in c.fetchall():
            module = inputmodule.InputModule(pid = row["pid"],
                                             id = row["id"],
                                             status = row["status"],
                                             config_file = row["config_file"])
            modules.append(module)
    return modules    
    
def logs(module_id):
    log_entries = []
    with _procdb_cursor() as c:
        c.execute("SELECT * FROM {table} WHERE module_id=?".format(table=schema.logs['table']),
                  [module_id])
        for row in c.fetchall():
            ts = time.localtime(row["timestamp"])
            
            log_entries.append("[{timestamp}] {log}".
                               format(timestamp = time.strftime("%d %b %Y %H:%M:%S",ts),
                                      log=row["line"]))
    return log_entries
                        
    
@contextlib.contextmanager
def _procdb_cursor():
    """opens the procdb sqlite database (creates it if needed)"""
    if (not os.path.isfile(PROC_DB)):
        _initialize_procdb()
    conn = sqlite3.connect(PROC_DB,timeout=5)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    yield c
    conn.commit()
    conn.close()

def _initialize_procdb():
    """create the procdb sqlite database"""
    conn = sqlite3.connect(PROC_DB)
    c = conn.cursor()
    for model in schema.schema:
        c.execute('CREATE TABLE {tn} (id INTEGER PRIMARY KEY)'.format(tn=model['table']))
        for column in model['columns']:
            c_name = column[0]
            if(c_name=='id'): #ignore the id field if present in the schema
                continue
            c_type = column[1]
            c.execute("ALTER TABLE {tn} ADD COLUMN '{cn}' {ct}"
                      .format(tn=model["table"],cn=c_name,ct=c_type))
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


def _get_module_by_column(column,value):
    with _procdb_cursor() as c:
        c.execute("SELECT * FROM {table} WHERE {column} = ?".
                  format(table=schema.modules['table'],column=column),(value,))
        row = c.fetchone()
    if row is None:
        return None

    module = inputmodule.InputModule(pid=row["pid"],
                                     id = row["id"],
                                     status=row["status"],
                                     config_file = row["config_file"])
    return module

def _insert_module(module,config_file):
    with _procdb_cursor() as c:
        #use string substitution to escape db_input_module insert
        data = [None, config_file, module.pid, module.status,module.name,module.destination.path]
        c.execute("INSERT INTO {table} VALUES (?,?,?,?,?,?)".format(table=schema.modules["table"]),
                  data)
        module.id = c.lastrowid
                  
def _get_numpy_client():
    return numpyclient.NumpyClient(NILMDB_URL)

class ProcDbError(Exception):
    """Base class for exceptions in this module"""

class ConfigError(ProcDbError):
    """Error caused by user misconfiguration"""
