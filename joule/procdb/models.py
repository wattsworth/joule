import collections

schema = [
  { 'name': "DbInputModules",
    'columns': [["name",             "string"],
                ["destination_path", "string"],
                ["status",           "string"]]
  }
]

DbInputModule = collections.namedtuple("DbInputModule",
                                       ["name",
                                        "destination_path",
                                        "status"])
