import unittest
from joule import api
import folder

async def setup():
    node = api.Node()
    """
    live
        sum1
        filt1
    arch
        sum1
        filt1
        free:
            stream1
            stream2
        """

def main():
    loader = unittest.TestLoader()
    tests = loader.loadTestsFromModule(folder)
    suite = unittest.TestSuite()
    suite.addTests(tests)
    runner = unittest.TextTestRunner()
    result = runner.run(suite)
    print(result)


if __name__ == '__main__':
    main()
    print("OK")