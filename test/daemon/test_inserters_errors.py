"""
Test the inserter and decimator objects
"""
import unittest
from joule.daemon import inserter, daemon
from unittest import mock
from test import helpers

class TestNilmDbDecimatorErrors(unittest.TestCase):

  def setUp(self):
    pass

  @mock.patch("joule.daemon.daemon.aionilmdb.AioNilmdb",autospec=True)      
  def test_error_if_source_does_not_exist(self, mock_client):
    
    #only /other/path exists in the database
    mock_info = helpers.mock_stream_info([["/other/path","uint8_1"]])
    mock_client.stream_list = mock.Mock(side_effect=mock_info)

    with self.assertRaisesRegex(daemon.DaemonError,"/base/path"):
      inserter.NilmDbDecimator(mock_client,"/base/path")

  @mock.patch("joule.daemon.daemon.aionilmdb.AioNilmdb",autospec=True)
  def test_error_if_nilmdb_returns_corrupt_layout(self, mock_client):
    #note: this should never happen but verify nilmdb response just to be safe
    bad_layout = "uint8_adsf"
    mock_info = helpers.mock_stream_info([["/base/path",bad_layout]])
    mock_client.stream_list = mock.Mock(side_effect=mock_info)

    with self.assertRaisesRegex(daemon.DaemonError,bad_layout):
      inserter.NilmDbDecimator(mock_client,"/base/path")
    
