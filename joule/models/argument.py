class Argument:

    def __init__(self, name: str, value: str):
        self.name = name
        self.value = value

    def __repr__(self):
        return "<Argument name=%s value=%s>" % (self.name, self.value)

    def __str__(self):
        return "%s=%s" % (self.name, self.value)
