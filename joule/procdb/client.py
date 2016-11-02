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
from joule.daemon import inputmodule

class SQLClient():

    def __init__(self,db_path,nilmdb_url):
        """opens the procdb sqlite database (creates it if needed)"""
        self.db_path = db_path
        self.nilmdb_url = nilmdb_url
        initialization_required = False
        if (not os.path.isfile(db_path)):
            initialization_required = True
        self.db = sqlite3.connect(db_path,timeout=5)
        self.db.row_factory = sqlite3.Row
        if(initialization_required):
            self._initialize_procdb()

        
    def register_input_module(self,input_module,config_file=""):
        """add an InputModule to the proc database"""
        dest = input_module.destination
        #1.) create a new path or ensure that
        #    the existing path matches input_module's datatype
        self._create_destination_path(dest)
        #2.) check if any other modules are using this path
        other_module = self._get_module_by_column("destination_path",dest.path)
        if(other_module):
            raise ConfigError("the path [%s] is being used by module [%s]"%
                              (dest.path,other_module.name))
        #3.) all good, register the module
        self._insert_module(input_module,config_file)

    def clear_input_modules(self):
        """remove all registered input modules"""
        with self.db:
            c = self.db.cursor()
            #use string substitution to escape db_input_module insert
            c.execute("DELETE FROM {table}".format(table=schema.modules['table']))

    def update_module(self,module):
        """udpate module statistics. COMMIT REQUIRED"""
        c = self.db.cursor()
        #these are the update-able fields in the module structure
        data = {'pid': module.pid,
                'status': module.status
        }
        fields = ",".join(["%s=?"%name for name in data.keys()])
        c.execute("UPDATE {table} SET {fields} WHERE id = ?".
                  format(table = schema.modules['table'],
                         fields = fields),(*data.values(),module.id))

    def find_module_by_name(self,module_name):
        return self._get_module_by_column("name",module_name)

    def find_module_by_id(self,module_id):
        return self._get_module_by_column("id",module_id)

    def find_module_by_dest_path(self,path):
        return self._get_module_by_column("destination_path",path)

    def log_to_module(self,line,module_id):
        """add a log line to the database associated with module_id
           REQUIRES a commit! """
        c = self.db.cursor()
        data = [None,line,module_id,int(time.time())]
        c.execute("INSERT INTO {table} VALUES (?,?,?,?)".format(table=schema.logs["table"]),
                  data)

    def commit(self):
        self.db.commit()
        
    def input_modules(self):
        modules = []
        c = self.db.cursor()
        c.execute("SELECT * FROM {table}".format(table=schema.modules['table']))
        for row in c.fetchall():
            module = inputmodule.InputModule(pid = row["pid"],
                                             id = row["id"],
                                             status = row["status"],
                                             config_file = row["config_file"])
            modules.append(module)
        return modules    

    def logs(self,module_id):
        log_entries = []

        c = self.db.cursor()
        c.execute("SELECT * FROM {table} WHERE module_id=?".format(table=schema.logs['table']),
                  [module_id])
        for row in c.fetchall():
            ts = time.localtime(row["timestamp"])

            log_entries.append("[{timestamp}] {log}".
                               format(timestamp = time.strftime("%d %b %Y %H:%M:%S",ts),
                                      log=row["line"]))
        return log_entries



    def _initialize_procdb(self):
        """create the procdb sqlite database"""
        with self.db:
            c=self.db.cursor()
            for model in schema.schema:
                c.execute('CREATE TABLE {tn} (id INTEGER PRIMARY KEY)'.format(tn=model['table']))
                for column in model['columns']:
                    c_name = column[0]
                    if(c_name=='id'): #ignore the id field if present in the schema
                        continue
                    c_type = column[1]
                    c.execute("ALTER TABLE {tn} ADD COLUMN '{cn}' {ct}"
                              .format(tn=model["table"],cn=c_name,ct=c_type))


    def _create_destination_path(self,destination):
        client = self._get_numpy_client()
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


    def _get_module_by_column(self,column,value):

        c = self.db.cursor()
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

    def _insert_module(self,module,config_file):
        with self.db:
            c = self.db.cursor()
            #use string substitution to escape db_input_module insert
            data = [None, config_file, module.pid, module.status,module.name,module.destination.path]
            c.execute("INSERT INTO {table} VALUES (?,?,?,?,?,?)".format(table=schema.modules["table"]),
                      data)
            module.id = c.lastrowid

    def _get_numpy_client(self):
        return numpyclient.NumpyClient(self.nilmdb_url)

class ProcDbError(Exception):
    """Base class for exceptions in this module"""

class ConfigError(ProcDbError):
    """Error caused by user misconfiguration"""
