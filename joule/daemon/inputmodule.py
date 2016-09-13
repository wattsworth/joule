class InputModule(object):
    def initialize(self,configs):
        print("initialized")

class InputModuleError(Exception):
    """Base class for exceptions in this module"""
    pass

