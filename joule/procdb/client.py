"""
Database interface to hold information
about the joule daemon and its processes
"""

import sqlite3
from . import schema
import os
import time
import logging
from joule.daemon import module, stream, element


class SQLClient():

    def __init__(self, db_path, max_log_lines):
        """opens the procdb sqlite database (creates it if needed)"""
        self.db_path = db_path
        self.max_log_lines = max_log_lines
        initialization_required = False
        if (not os.path.isfile(db_path)):
            initialization_required = True
        self.db = sqlite3.connect(db_path, timeout=5)
        self.db.row_factory = sqlite3.Row
        if(initialization_required):
            self._initialize_procdb()
        # turn off synchronous mode to speed up commits
        c = self.db.cursor()
        c.execute("PRAGMA synchronous=OFF")

    def commit(self):
        self.db.commit()

    def clear_db(self):
        """remove all registered input modules"""
        with self.db:
            c = self.db.cursor()
            # use string substitution to escape db_input_module insert
            for table in schema.models:
                c.execute("DELETE FROM {table}".format(table=table['table']))

    def register_module(self, my_module):
        """add a Module to the proc database"""
        c = self.db.cursor()
        # use string substitution to escape db_input_module insert
        data = [None,  my_module.pid, my_module.status,
                my_module.name, my_module.description, my_module.exec_cmd]
        c.execute("INSERT INTO {table} VALUES (?,?,?,?,?,?)".
                  format(table=schema.modules["table"]), data)
        my_module.id = c.lastrowid

        # link this module's outputs with existing streams

        for (name, path) in my_module.output_paths.items():
            self._link_by_path(my_module, name, path, "output")
        for (name, path) in my_module.input_paths.items():
            self._link_by_path(my_module, name, path, "input")

#        print("added module %d with name [%s]"%(my_module.id,my_module.name))
    def update_module(self, my_module):
        """udpate module statistics. COMMIT REQUIRED"""
        c = self.db.cursor()
        # these are the update-able fields in the module structure
        data = {'pid': my_module.pid,
                'status': my_module.status
                }
        fields = ",".join(["%s=?" % name for name in data.keys()])
        c.execute("UPDATE {table} SET {fields} WHERE id = ?".
                  format(table=schema.modules['table'],
                         fields=fields), (*data.values(), my_module.id))

    def add_log_by_module(self, line, module_id):
        """add a log line to the database associated with module_id
           REQUIRES a commit! """
        c = self.db.cursor()
        data = [None, line, module_id, int(time.time())]
        cmd = "INSERT INTO {table} VALUES (?,?,?,?)".\
              format(table=schema.logs["table"])
        c.execute(cmd, data)
        # limit number of logs per module
        cmd = """
        DELETE FROM logs WHERE module_id = ? AND id <=
          (SELECT id FROM logs WHERE module_id = ?
           ORDER BY id DESC LIMIT 1 OFFSET ?);
         """ 
        data = [module_id, module_id, self.max_log_lines]
        c.execute(cmd, data)

    def find_module_by_name(self, module_name):
        return self._find_module_by_column("name", module_name)

    def find_module_by_id(self, module_id):
        return self._find_module_by_column("id", module_id)

    def find_all_modules(self):
        modules = []
        c = self.db.cursor()
        c.execute(
            "SELECT * FROM {table}".format(table=schema.modules['table']))
        for row in c.fetchall():
            attribs = {**row}
            attribs['input_paths'] = {}
            attribs['output_paths'] = {}
            my_module = module.Module(**attribs)
            self._set_module_paths(my_module)
            modules.append(my_module)
        return modules

    def find_logs_by_module(self, module_id):
        log_entries = []

        c = self.db.cursor()
        c.execute("SELECT * FROM {table} WHERE module_id=?".format(table=schema.logs['table']),
                  [module_id])
        for row in c.fetchall():
            ts = time.localtime(row["timestamp"])

            log_entries.append("[{timestamp}] {log}".
                               format(timestamp=time.strftime("%d %b %Y %H:%M:%S", ts),
                                      log=row["line"]))
        return log_entries

    def register_stream(self, my_stream):
        """add a Stream to the proc database"""
        c = self.db.cursor()
        # use string substitution to escape db_input_module insert
        data = [None, my_stream.name, my_stream.description,
                my_stream.keep_us, my_stream.decimate, my_stream.datatype, my_stream.path]
        c.execute("INSERT INTO {table} VALUES (?,?,?,?,?,?,?)".
                  format(table=schema.streams["table"]), data)
        my_stream.id = c.lastrowid
        for my_element in my_stream.elements:
            self._add_element(my_stream, my_element)

    def find_streams_by_module(self, module_id, direction):
        c = self.db.cursor()
        if(direction != "input" and direction != "output"):
            raise ProcDbError(
                "[direction] is invalid, must be soure|output")

        c.execute("SELECT streams.* FROM streams_modules " +
                  "JOIN modules ON streams_modules.module_id=modules.id " +  # TODO: remove?
                  "JOIN streams ON streams_modules.stream_id=streams.id " +
                  "WHERE streams_modules.direction=? AND streams_modules.module_id=?;",
                  (direction, module_id))

        streams = []
        for row in c.fetchall():
            my_stream = stream.Stream(**row)
            self._set_stream_elements(my_stream)
            streams.append(my_stream)

        return streams

    def find_stream_by_id(self, id):
        return self._find_stream_by_column("id", id)

    def find_stream_by_name(self, name):
        return self._find_stream_by_column("name", name)

    def find_stream_by_path(self, path):
        return self._find_stream_by_column("path", path)

    def find_all_streams(self):
        streams = []
        c = self.db.cursor()
        c.execute(
            "SELECT * FROM {table}".format(table=schema.streams['table']))
        for row in c.fetchall():
            my_stream = stream.Stream(**row)
            self._set_stream_elements(my_stream)
            streams.append(my_stream)
        return streams

    def _initialize_procdb(self):
        """create the procdb sqlite database"""
        with self.db:
            c = self.db.cursor()
            for model in schema.models:
                c.execute('CREATE TABLE {tn} (id INTEGER PRIMARY KEY)'.format(
                    tn=model['table']))
                for column in model['columns']:
                    c_name = column[0]
                    # ignore the id field if present in the schema
                    if(c_name == 'id'):
                        continue
                    c_type = column[1]
                    c.execute("ALTER TABLE {tn} ADD COLUMN '{cn}' {ct}"
                              .format(tn=model["table"], cn=c_name, ct=c_type))

    def _find_module_by_column(self, column, value):
        c = self.db.cursor()
        c.execute("SELECT * FROM {table} WHERE {column} = ?".
                  format(table=schema.modules['table'], column=column), (value,))
        row = c.fetchone()
        if row is None:
            return None
        attribs = {**row}
        attribs['input_paths'] = {}
        attribs['output_paths'] = {}
        my_module = module.Module(**attribs)
        self._set_module_paths(my_module)
        return my_module

    def _find_stream_by_column(self, column, value):
        c = self.db.cursor()
        c.execute("SELECT * FROM {table} WHERE {column} = ?".
                  format(table=schema.streams['table'], column=column), (value,))
        row = c.fetchone()
        if row is None:
            return None
        my_stream = stream.Stream(**row)
        self._set_stream_elements(my_stream)
        return my_stream

    def _set_module_paths(self, my_module):
        c = self.db.cursor()
        c.execute("SELECT streams_modules.name, streams_modules.direction, streams.path " +
                  "FROM streams_modules " +
                  "JOIN streams ON streams_modules.stream_id = streams.id " +
                  "WHERE streams_modules.module_id=?", (my_module.id,))
        for row in c.fetchall():
            name = row['name']
            path = row['path']
            if(row['direction'] == 'input'):
                my_module.input_paths[name] = path
            else:
                my_module.output_paths[name] = path

    def _link_by_path(self, my_module, name, path, direction):
        c = self.db.cursor()
        stream = self._find_stream_by_column('path', path)
        if(stream is None):
            logging.error("[%s]: stream [%s] is not in the database" %
                          (my_module.name, path))
        else:
            data = [None, name, stream.id, my_module.id, direction]
            c.execute("INSERT INTO {table} VALUES (?,?,?,?,?)".
                      format(table=schema.streams_modules["table"]), data)

    def _add_element(self, stream, element):
        c = self.db.cursor()
        data = [None, stream.id, *element]
        c.execute("INSERT INTO {table} VALUES (?,?,?,?,?,?,?,?,?,?)".
                  format(table=schema.elements["table"]), data)

    def _set_stream_elements(self, stream):
        c = self.db.cursor()
        c.execute("SELECT * FROM {table} WHERE stream_id= ? ".
                  format(table=schema.elements["table"]), (stream.id,))
        for row in c.fetchall():
            attribs = {key: value for key, value in {**row}.items()
                       if key not in ["id", "stream_id"]}
            stream.elements.append(element.Element(**attribs))


class ProcDbError(Exception):
    """Base class for exceptions in this module"""


class ConfigError(ProcDbError):
    """Error caused by user misconfiguration"""
