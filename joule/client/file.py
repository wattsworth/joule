
from joule.client.reader import ReaderModule


class FileReader(ReaderModule):
    "Read data from a file"

    def __init__(self):
        super(FileReader, self).__init__("Random Reader")

#    def description(self):
#        return "read data from a file"
    
    def custom_args(self, parser):
        parser.add_argument("-f", "--file", required=True,
                            help="file name")
        parser.add_argument("-t", "--timestamp", action="store_true",
                            help="apply timestamps to data")

    async def process(self, parsed_args, output):
        print("running with f=%s and t=%s" % (
            parsed_args.file, parsed_args.timestamp))

        
if __name__ == "__main__":
    r = FileReader()
    r.run()
    
