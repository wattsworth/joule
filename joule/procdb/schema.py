
modules = {'table': "modules",
           'columns': [
               ["id",           "integer primary key"],
               ["pid",          "integer"],
               ["status",       "string"],
               ["name",         "string"],
               ["description", "string"],
               ["exec_cmd", "string"]]
           }
streams = {'table': "streams",
           'columns': [
               ["id",           "integer primary key"],
               ["name",         "string"],
               ["description",  "string"],
               ["keep_us",      "integer"],
               ["decimate",     "integer"],
               ["datatype",     "string"],
               ["path",         "string"]]
           }
streams_modules = {'table': "streams_modules",
                   'columns': [
                       ["id",          "integer primary key"],
                       ["name",        "integer"],
                       ["stream_id",   "integer"],
                       ["module_id",   "integer"],
                       ["direction",   "string"]]  # input,output
                   }
elements = {'table': "elements",
            'columns': [
                ["id",           "integer primary key"],
                ["stream_id",    "integer"],
                ["name",         "string"],
                ["units",        "string"],
                ["plottable",    "integer"],
                ["discrete",     "integer"],
                ["offset",       "float"],
                ["scale_factor", "float"],
                ["default_max",  "float"],
                ["default_min",  "float"]]
            }

logs = {'table': "logs",
        'columns': [
            ["id",             "integer primary key"],
            ["line",           "string"],
            ["module_id",      "integer"],
            ["timestamp",      "integer"]]
        }
models = [
    modules,
    streams,
    streams_modules,  # join table
    elements,
    logs
]
