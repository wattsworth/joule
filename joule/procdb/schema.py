

modules = { 'table': "modules",
            'columns': [
              ["id",          "integer primary key"],
              ["config_file", "string"],              
              ["pid",         "integer"],
              ["status",      "string"],
              ["name",        "string"],
              ["destination_path", "string"]]
}

logs = { 'table': "logs",
         'columns': [
           ["id", "integer primary key"],
           ["line", "string"],
           ["module_id", "integer"],
           ["timestamp", "integer"]]
}
schema = [
  modules,
  logs
]
