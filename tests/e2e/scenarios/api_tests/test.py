#!/usr/bin/env python3
import time
import io

import unittest
from joule import api
import folder, stream, module, data

def main():
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    suite.addTests(loader.loadTestsFromModule(folder))
    suite.addTests(loader.loadTestsFromModule(stream))
    suite.addTests(loader.loadTestsFromModule(module))
    suite.addTests(loader.loadTestsFromModule(data))
    output = io.StringIO()
    runner = unittest.TextTestRunner(failfast=True, verbosity=2)
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
    print("...running tests")
    exit(main())
