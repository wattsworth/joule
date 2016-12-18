"""
Test the inserter and decimator objects
"""

from joule.daemon import inserter, daemon, aionilmdb
from unittest import mock
from test import helpers
import asynctest
import asyncio


class TestNilmDbDecimatorErrors(asynctest.TestCase):

    def setUp(self):
        pass

    def test_error_if_source_does_not_exist(self):

        # only /other/path exists in the database
        mock_info = helpers.mock_stream_info([["/other/path", "uint8_1"]])

        mock_client = mock.Mock(autospec=aionilmdb.AioNilmdb)
        mock_client.stream_list = \
            asynctest.mock.CoroutineMock(side_effect=mock_info)

        my_decimator = inserter.NilmDbDecimator(mock_client, "/base/path")
        with self.assertRaisesRegex(daemon.DaemonError, "/base/path"):
            # initialization is lazy so we have to process some data
            loop = asyncio.get_event_loop()
            data = helpers.create_data("int32_4", length=1)
            loop.run_until_complete(my_decimator.process(data))

    def test_error_if_nilmdb_returns_corrupt_layout(self):
        """ note: this should never happen but
        verify nilmdb response just to be safe"""
        bad_layout = "uint8_adsf"
        mock_info = helpers.mock_stream_info([["/base/path", bad_layout]])
        mock_client = mock.Mock(autospec=aionilmdb.AioNilmdb)
        mock_client.stream_list = \
            asynctest.mock.CoroutineMock(side_effect=mock_info)

        my_decimator = inserter.NilmDbDecimator(mock_client, "/base/path")
        with self.assertRaisesRegex(daemon.DaemonError, bad_layout):
            # initialization is lazy so we have to process some data
            loop = asyncio.get_event_loop()
            data = helpers.create_data("int32_4", length=1)
            loop.run_until_complete(my_decimator.process(data))
