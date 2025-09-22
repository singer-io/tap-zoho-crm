import unittest
from unittest.mock import patch, MagicMock
from tap_zoho_crm.streams.abstracts import IncrementalStream

class ConcreteParentBaseStream(IncrementalStream):
    @property
    def key_properties(self):
        return ["id"]

    @property
    def replication_keys(self):
        return ["updated_at"]

    @property
    def replication_method(self):
        return "INCREMENTAL"

    @property
    def tap_stream_id(self):
        return "stream_1"

class TestSync(unittest.TestCase):
    @patch("tap_zoho_crm.streams.abstracts.metadata.to_map")
    def setUp(self, mock_to_map):

        mock_catalog = MagicMock()
        mock_catalog.schema.to_dict.return_value = {"key": "value"}
        mock_catalog.metadata = "mock_metadata"
        mock_to_map.return_value = {"metadata_key": "metadata_value"}

        self.stream = ConcreteParentBaseStream(catalog=mock_catalog)
        self.stream.client = MagicMock()
        self.stream.child_to_sync = []

    @patch("tap_zoho_crm.streams.abstracts.get_bookmark", return_value=100)
    def test_write_bookmark_with_state(self, mock_get_bookmark):
        """Verifies that the bookmark is updated when the new value is
        greater than the old one."""

        state = {'bookmarks': {'test_stream': {'updated_at': 100}}}
        result = self.stream.write_bookmark(state, "test_stream", "updated_at", 200)
        self.assertEqual(result, {'bookmarks': {'test_stream': {'updated_at': 200}}})

    @patch("tap_zoho_crm.streams.abstracts.get_bookmark", return_value=100)
    def test_write_bookmark_without_state(self, mock_get_bookmark):
        """Verifies that the bookmark structure is created and the value is set."""
        state = {}
        result = self.stream.write_bookmark(state, "test_stream", "updated_at", 200)
        self.assertEqual(result, {'bookmarks': {'test_stream': {'updated_at': 200}}})

    @patch("tap_zoho_crm.streams.abstracts.get_bookmark", return_value=300)
    def test_write_bookmark_with_old_value(self, mock_get_bookmark):
        """Test that a bookmark is not updated if the new value is
        less than or equal to the existing bookmark value."""
        state = {'bookmarks': {'test_stream': {'updated_at': 300}}}
        result = self.stream.write_bookmark(state, "test_stream", "updated_at", 200)
        self.assertEqual(result, {'bookmarks': {'test_stream': {'updated_at': 300}}})

