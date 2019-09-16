#!/usr/bin/env python3
import time
import io

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
    output = io.StringIO()
    runner = unittest.TextTestRunner(stream=output, failfast=True)
    result = runner.run(suite)
    if result.wasSuccessful():
        print("OK")
        return 0
    else:
        print("FAIL")
        output.seek(0)
        print(output.read())
        return -1


if __name__ == '__main__':
    time.sleep(1)
    exit(main())
