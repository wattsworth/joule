

modules = { 'table': "modules",
            'columns': [
              ["id",          "integer primary key"],
              ["config_file", "string"],              
              ["pid",         "string"],
              ["status",      "string"],
              ["destination_path", "string"]]
}

schema = [
  modules
]
