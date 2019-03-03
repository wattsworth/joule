import unittest
from joule import api
import folder, stream, module, data

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

    suite = unittest.TestSuite()
    suite.addTests(loader.loadTestsFromModule(folder))
    suite.addTests(loader.loadTestsFromModule(stream))
    suite.addTests(loader.loadTestsFromModule(module))
    suite.addTests(loader.loadTestsFromModule(data))
    runner = unittest.TextTestRunner()
    result = runner.run(suite)
    print(result)


if __name__ == '__main__':
    main()
    print("OK")