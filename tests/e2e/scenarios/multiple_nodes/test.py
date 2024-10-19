#!/usr/bin/env python3
import time
import io
import unittest
import basic


def main():
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    suite.addTests(loader.loadTestsFromModule(basic))
    output = io.StringIO()
    runner = unittest.TextTestRunner(stream=output, failfast=True)
    result = runner.run(suite)
    if result.wasSuccessful():
        print("OK")
    else:
        print("FAIL")
        output.seek(0)
        print(output.read())


if __name__ == '__main__':
    time.sleep(1)
    main()
