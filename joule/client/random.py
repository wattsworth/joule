
from joule.client.reader import ReaderModule


class RandomReader(ReaderModule):
    "Generate a random stream of data"

    def __init__(self):
        super(RandomReader, self).__init__("Random Reader")

    def description(self):
        return "generate a random stream of data"

    def help(self):
        return """
        This is a module that generates random numbers.
        Specify width and the rate:
        Example:
            $> joule reader random 3 10
            1234 45 82 -33
            1234 45 82 -33
            1234 45 82 -33
            1234 45 82 -33
            1234 45 82 -33
        """
    
    def custom_args(self, parser):
        parser.add_argument("width", type=int,
                            help="number of elements in output")
        parser.add_argument("rate", type=float,
                            help="rate in Hz")

    async def process(self, parsed_args, output):
        print("running with w=%d and r=%d" % (
            parsed_args.width, parsed_args.rate))

        
if __name__ == "__main__":
    r = RandomReader()
    r.run()
    
