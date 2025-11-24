import unittest

from joule.utilities import connection_info
from joule.errors import ApiError

class TestConnectionInfoErrors(unittest.TestCase):
    # the rest of ConnectionInfo is already covered by other tests
    def test_missing_parameters(self):
        with self.assertRaises(ApiError):
            connection_info.from_json({
                "username":"test",
                "password":"password",
                "port":123,
                "database":"database"
                # missing host parameters
            })
        