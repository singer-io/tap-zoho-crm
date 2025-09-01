import unittest
from unittest.mock import patch, MagicMock
from tap_zoho_crm.sync import write_schema, sync, update_currently_syncing
from tap_zoho_crm.sync import build_dynamic_stream
from tap_zoho_crm.streams.abstracts import FullTableStream, IncrementalStream
from tap_zoho_crm.streams import Currencies, Organization

STREAMS = {
    "currencies": Currencies,
    "organization": Organization
    }


class TestSync(unittest.TestCase):

    def test_write_schema_only_parent_selected(self):
        mock_stream = MagicMock()
        mock_stream.is_selected.return_value = True
        mock_stream.children = ["organization", "currencies"]
        mock_stream.child_to_sync = []

        client = MagicMock()
        catalog = MagicMock()
        catalog.get_stream.return_value = MagicMock()

        write_schema(mock_stream, client, [], catalog)

        mock_stream.write_schema.assert_called_once()
        self.assertEqual(len(mock_stream.child_to_sync), 0)

    @patch("singer.write_schema")
    @patch("singer.get_currently_syncing")
    @patch("singer.Transformer")
    @patch("singer.write_state")
    @patch("tap_zoho_crm.streams.abstracts.IncrementalStream.sync")
    def test_sync_stream1_called(self, mock_sync, mock_write_state, mock_transformer, mock_get_currently_syncing, mock_write_schema):
        mock_catalog = MagicMock()
        currency_stream = MagicMock()
        currency_stream.stream = "currencies"
        profile_stream = MagicMock()
        profile_stream.stream = "profiles"
        mock_catalog.get_selected_streams.return_value = [
            currency_stream,
            profile_stream
        ]
        state = {}

        client = MagicMock()
        config = {}

        sync(client, config, mock_catalog, state)

        self.assertEqual(mock_sync.call_count, 2)

    @patch("singer.get_currently_syncing")
    @patch("singer.set_currently_syncing")
    @patch("singer.write_state")
    def test_remove_currently_syncing(self, mock_write_state, mock_set_currently_syncing, mock_get_currently_syncing):
        mock_get_currently_syncing.return_value = "some_stream"
        state = {"currently_syncing": "some_stream"}

        update_currently_syncing(state, None)

        mock_get_currently_syncing.assert_called_once_with(state)
        mock_set_currently_syncing.assert_not_called()
        mock_write_state.assert_called_once_with(state)
        self.assertNotIn("currently_syncing", state)

    @patch("singer.get_currently_syncing")
    @patch("singer.set_currently_syncing")
    @patch("singer.write_state")
    def test_set_currently_syncing(self, mock_write_state, mock_set_currently_syncing, mock_get_currently_syncing):
        mock_get_currently_syncing.return_value = None
        state = {}

        update_currently_syncing(state, "new_stream")

        mock_get_currently_syncing.assert_not_called()
        mock_set_currently_syncing.assert_called_once_with(state, "new_stream")
        mock_write_state.assert_called_once_with(state)
        self.assertNotIn("currently_syncing", state)

    @patch("tap_zoho_crm.sync.metadata.to_map")
    def test_build_dynamic_stream_full_table(self, mock_to_map):
        """Test build_dynamic_stream returns FullTableStream subclass when method is FULL_TABLE."""
        mock_to_map.return_value = {
            (): {
                "forced-replication-method": "FULL_TABLE",
                "valid-replication-keys": ["id"]
            }
        }

        catalog_entry = MagicMock()
        catalog_entry.stream = "accounts"
        catalog_entry.key_properties = ["id"]
        catalog_entry.metadata = "mock_metadata"

        mock_client = MagicMock()

        stream_instance = build_dynamic_stream(mock_client, catalog_entry)

        self.assertIsInstance(stream_instance, FullTableStream)
        self.assertEqual(stream_instance.tap_stream_id, "accounts")
        self.assertEqual(stream_instance.key_properties, ["id"])
        self.assertEqual(stream_instance.replication_method, "FULL_TABLE")
        self.assertEqual(stream_instance.replication_keys, ["id"])
        self.assertEqual(stream_instance.path, "accounts")
        self.assertEqual(stream_instance.data_key, "data")
        self.assertTrue(stream_instance.is_dynamic)

    @patch("tap_zoho_crm.sync.metadata.to_map")
    def test_build_dynamic_stream_incremental(self, mock_to_map):
        """Test build_dynamic_stream returns IncrementalStream subclass when method is INCREMENTAL."""

        mock_to_map.return_value = {
            (): {
                "forced-replication-method": "INCREMENTAL",
                "valid-replication-keys": ["updated_at"]
            }
        }

        catalog_entry = MagicMock()
        catalog_entry.stream = "contacts"
        catalog_entry.key_properties = ["id"]
        catalog_entry.metadata = "mock_metadata"

        mock_client = MagicMock()

        stream_instance = build_dynamic_stream(mock_client, catalog_entry)

        self.assertIsInstance(stream_instance, IncrementalStream)
        self.assertEqual(stream_instance.tap_stream_id, "contacts")
        self.assertEqual(stream_instance.replication_method, "INCREMENTAL")
        self.assertEqual(stream_instance.replication_keys, ["updated_at"])

