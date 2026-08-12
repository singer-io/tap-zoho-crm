import unittest
from unittest.mock import patch, MagicMock
from singer.catalog import Catalog
from tap_zoho_crm.discover import discover


SAMPLE_SCHEMA = {
    "type": "object",
    "properties": {
        "id": {"type": ["null", "string"]},
        "updated_at": {"type": ["null", "string"], "format": "date-time"}
    }
}
SAMPLE_MDATA = [
    {
        "breadcrumb": [],
        "metadata": {
            "table-key-properties": ["id"],
            "forced-replication-method": "INCREMENTAL",
            "valid-replication-keys": ["updated_at"]
        }
    }
]


class TestDiscover(unittest.TestCase):

    @patch('tap_zoho_crm.discover.get_dynamic_schema')
    @patch('tap_zoho_crm.discover.get_static_schemas')
    def test_discover_returns_catalog_with_merged_streams(self, mock_static, mock_dynamic):
        """Test that discover() merges static and dynamic schemas into a Catalog."""
        mock_static.return_value = (
            {"users": SAMPLE_SCHEMA},
            {"users": SAMPLE_MDATA}
        )
        mock_dynamic.return_value = (
            {"accounts": SAMPLE_SCHEMA},
            {"accounts": SAMPLE_MDATA}
        )

        mock_client = MagicMock()
        result = discover(mock_client)

        self.assertIsInstance(result, Catalog)
        stream_ids = [s.tap_stream_id for s in result.streams]
        self.assertIn("users", stream_ids)
        self.assertIn("accounts", stream_ids)
        mock_static.assert_called_once()
        mock_dynamic.assert_called_once_with(mock_client)

    @patch('tap_zoho_crm.discover.get_dynamic_schema')
    @patch('tap_zoho_crm.discover.get_static_schemas')
    def test_discover_stream_names_are_lowercased(self, mock_static, mock_dynamic):
        """Test that stream names in catalog entries are lowercased."""
        mock_static.return_value = (
            {"Users": SAMPLE_SCHEMA},
            {"Users": SAMPLE_MDATA}
        )
        mock_dynamic.return_value = ({}, {})

        mock_client = MagicMock()
        result = discover(mock_client)

        self.assertEqual(result.streams[0].tap_stream_id, "users")

    @patch('tap_zoho_crm.discover.get_dynamic_schema')
    @patch('tap_zoho_crm.discover.get_static_schemas')
    def test_discover_raises_on_invalid_schema(self, mock_static, mock_dynamic):
        """Test that discover() logs and re-raises when Schema.from_dict fails."""
        mock_static.return_value = (
            {"bad_stream": "not_a_dict"},
            {"bad_stream": SAMPLE_MDATA}
        )
        mock_dynamic.return_value = ({}, {})

        mock_client = MagicMock()

        with patch('tap_zoho_crm.discover.Schema.from_dict', side_effect=Exception("Invalid")):
            with self.assertRaises(Exception) as ctx:
                discover(mock_client)

        self.assertIn("Invalid", str(ctx.exception))

    @patch('tap_zoho_crm.discover.get_dynamic_schema')
    @patch('tap_zoho_crm.discover.get_static_schemas')
    def test_discover_key_properties_from_metadata(self, mock_static, mock_dynamic):
        """Test that key_properties are read from metadata in the catalog entry."""
        mock_static.return_value = (
            {"currencies": SAMPLE_SCHEMA},
            {"currencies": SAMPLE_MDATA}
        )
        mock_dynamic.return_value = ({}, {})

        mock_client = MagicMock()
        result = discover(mock_client)

        self.assertEqual(result.streams[0].key_properties, ["id"])
