import joule.utils.time

   
class StreamInfo(object):

    def __init__(self, url, info):
        self.url = url
        self.info = info
        self.total_count = 0
        self.timestamp_min = 0
        self.timestamp_max = 0
        self.rows = 0
        self.seconds = 0
        try:
            self.path = info[0]
            self.layout = info[1]
            self.layout_type = self.layout.split('_')[0]
            self.layout_count = int(self.layout.split('_')[1])
            self.total_count = self.layout_count + 1
            self.timestamp_min = info[2]
            self.timestamp_max = info[3]
            self.rows = info[4]
            self.seconds = joule.utils.time.timestamp_to_seconds(info[5])
        except IndexError as TypeError:
            pass

    def string(self, interhost):
        """Return stream info as a string.  If interhost is true,
        include the host URL."""
        if interhost:
            return "[%s] " % (self.url) + str(self)
        return str(self)

    def __str__(self):
        """Return stream info as a string."""
        return "%s (%s), %.2fM rows, %.2f hours" % (
            self.path, self.layout, self.rows / 1e6,
            self.seconds / 3600.0)
