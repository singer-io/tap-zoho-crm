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
        currency_stream.tap_stream_id = "currencies"
        user_stream = MagicMock()
        user_stream.stream = "users"
        user_stream.tap_stream_id = "users"
        mock_catalog.get_selected_streams.return_value = [
            currency_stream,
            user_stream
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

    def test_build_dynamic_stream_full_table(self):
        """Test build_dynamic_stream returns FullTableStream subclass when method is FULL_TABLE."""
        catalog_entry = MagicMock()
        catalog_entry.stream = "accounts"
        catalog_entry.tap_stream_id = "accounts"
        catalog_entry.key_properties = ["id"]

        # Here's the mocked metadata (as a raw dict)
        catalog_entry.metadata = [
            {
                "breadcrumb": [],
                "metadata": {
                    "tap_stream_id": "accounts",
                    "forced-replication-method": "FULL_TABLE",
                    "valid-replication-keys": ["id"]
                }
            }
        ]

        mock_client = MagicMock()
        stream_instance = build_dynamic_stream(mock_client, catalog_entry, "Accounts")

        self.assertIsInstance(stream_instance, FullTableStream)
        self.assertEqual(stream_instance.tap_stream_id, "accounts")
        self.assertEqual(stream_instance.key_properties, ["id"])
        self.assertEqual(stream_instance.replication_method, "FULL_TABLE")
        self.assertEqual(stream_instance.replication_keys, ["id"])
        self.assertEqual(stream_instance.path, "Accounts")
        self.assertEqual(stream_instance.data_key, "data")
        self.assertTrue(stream_instance.is_dynamic)

    def test_build_dynamic_stream_incremental(self):
        """Test build_dynamic_stream returns IncrementalStream subclass when method is INCREMENTAL."""
        catalog_entry = MagicMock()
        catalog_entry.stream = "contacts"
        catalog_entry.tap_stream_id = "contacts"
        catalog_entry.key_properties = ["id"]
        catalog_entry.metadata = [
            {
                "breadcrumb": [],
                "metadata": {
                    "tap_stream_id": "contacts",
                    "forced-replication-method": "INCREMENTAL",
                    "valid-replication-keys": ["updated_at"]
                }
            }
        ]

        mock_client = MagicMock()
        stream_instance = build_dynamic_stream(mock_client, catalog_entry, "Contacts")

        self.assertIsInstance(stream_instance, IncrementalStream)
        self.assertEqual(stream_instance.tap_stream_id, "contacts")
        self.assertEqual(stream_instance.replication_method, "INCREMENTAL")
        self.assertEqual(stream_instance.replication_keys, ["updated_at"])
        self.assertEqual(stream_instance.path, "Contacts")

    # ------------------------------------------------------------------
    # write_schema: child appended when child IS in streams_to_sync
    # ------------------------------------------------------------------

    def test_write_schema_appends_child_when_in_streams_to_sync(self):
        """child_to_sync is populated when the child stream is in streams_to_sync."""
        mock_stream = MagicMock()
        mock_stream.is_selected.return_value = True
        mock_stream.children = ["currencies"]
        mock_stream.child_to_sync = []

        client = MagicMock()
        catalog = MagicMock()
        catalog.get_stream.return_value = MagicMock()

        write_schema(mock_stream, client, ["currencies"], catalog)

        self.assertEqual(len(mock_stream.child_to_sync), 1)

    # ------------------------------------------------------------------
    # deselect_unselected_fields
    # ------------------------------------------------------------------

    def test_deselect_unselected_fields_marks_unselected(self):
        """Fields with no 'selected' key are deselected."""
        from tap_zoho_crm.sync import deselect_unselected_fields
        from singer import metadata as singer_metadata

        mdata = singer_metadata.new()
        mdata = singer_metadata.write(mdata, (), 'table-key-properties', ['id'])
        mdata = singer_metadata.write(mdata, ('properties', 'id'), 'inclusion', 'automatic')
        mdata = singer_metadata.write(mdata, ('properties', 'name'), 'inclusion', 'available')
        mdata_list = singer_metadata.to_list(mdata)

        catalog_entry = MagicMock()
        catalog_entry.metadata = mdata_list

        deselect_unselected_fields(catalog_entry)

        updated_map = singer_metadata.to_map(catalog_entry.metadata)
        # 'name' field had no 'selected' key → should now be False
        self.assertFalse(updated_map.get(('properties', 'name'), {}).get('selected'))

    def test_deselect_unselected_fields_skips_root_breadcrumb(self):
        """The root breadcrumb () is skipped (truthy check on breadcrumb)."""
        from tap_zoho_crm.sync import deselect_unselected_fields
        from singer import metadata as singer_metadata

        mdata = singer_metadata.new()
        mdata = singer_metadata.write(mdata, (), 'table-key-properties', ['id'])
        mdata_list = singer_metadata.to_list(mdata)

        catalog_entry = MagicMock()
        catalog_entry.metadata = mdata_list

        # Should not raise or modify root breadcrumb
        deselect_unselected_fields(catalog_entry)
        updated_map = singer_metadata.to_map(catalog_entry.metadata)
        self.assertNotIn('selected', updated_map.get((), {}))

    # ------------------------------------------------------------------
    # sync(): dynamic stream path (stream not in STREAMS)
    # ------------------------------------------------------------------

    @patch("tap_zoho_crm.sync.build_dynamic_stream")
    @patch("tap_zoho_crm.sync.get_dynamic_schema")
    @patch("singer.write_schema")
    @patch("singer.get_currently_syncing", return_value=None)
    @patch("singer.Transformer")
    @patch("singer.write_state")
    def test_sync_uses_dynamic_stream_for_unknown_stream(
        self,
        mock_write_state,
        mock_transformer,
        mock_get_syncing,
        mock_write_schema,
        mock_get_dynamic_schema,
        mock_build_dynamic,
    ):
        """sync() calls build_dynamic_stream for streams not in STREAMS."""
        from tap_zoho_crm.sync import sync

        mock_get_dynamic_schema.return_value = ({"Contacts": {}}, {})

        dynamic_stream = MagicMock()
        dynamic_stream.parent = None
        dynamic_stream.children = []
        dynamic_stream.child_to_sync = []
        dynamic_stream.is_selected.return_value = True
        dynamic_stream.sync.return_value = 0
        mock_build_dynamic.return_value = dynamic_stream

        stream_entry = MagicMock()
        stream_entry.tap_stream_id = "contacts"

        mock_catalog = MagicMock()
        mock_catalog.get_selected_streams.return_value = [stream_entry]
        mock_catalog.get_stream.return_value = MagicMock()

        mock_transformer_ctx = MagicMock()
        mock_transformer.return_value.__enter__ = MagicMock(return_value=mock_transformer_ctx)
        mock_transformer.return_value.__exit__ = MagicMock(return_value=False)

        client = MagicMock()
        sync(client, {}, mock_catalog, {})

        mock_build_dynamic.assert_called_once()
        dynamic_stream.sync.assert_called_once()

    # ------------------------------------------------------------------
    # sync(): stream with parent not in streams_to_sync → parent added
    # ------------------------------------------------------------------

    @patch("tap_zoho_crm.sync.get_dynamic_schema")
    @patch("singer.get_currently_syncing", return_value=None)
    @patch("singer.write_schema")
    @patch("singer.Transformer")
    @patch("singer.write_state")
    def test_sync_adds_parent_when_child_selected_without_parent(
        self,
        mock_write_state,
        mock_transformer,
        mock_write_schema,
        mock_get_syncing,
        mock_get_dynamic_schema,
    ):
        """When a child stream is selected but its parent is not, the parent is added."""
        from tap_zoho_crm.sync import sync

        mock_get_dynamic_schema.return_value = ({}, {})

        # Use a real static stream that has a parent (Currencies has no parent, but
        # we can mock a stream object with parent attribute set)
        child_stream_mock = MagicMock()
        child_stream_mock.parent = "currencies"
        child_stream_mock.children = []
        child_stream_mock.child_to_sync = []

        parent_stream_mock = MagicMock()
        parent_stream_mock.parent = None
        parent_stream_mock.children = []
        parent_stream_mock.child_to_sync = []
        parent_stream_mock.is_selected.return_value = True
        parent_stream_mock.sync.return_value = 0

        child_entry = MagicMock()
        child_entry.tap_stream_id = "organization"  # not in STREAMS to force build_dynamic

        mock_catalog = MagicMock()
        mock_catalog.get_selected_streams.return_value = [child_entry]
        mock_catalog.get_stream.return_value = MagicMock()

        mock_transformer_ctx = MagicMock()
        mock_transformer.return_value.__enter__ = MagicMock(return_value=mock_transformer_ctx)
        mock_transformer.return_value.__exit__ = MagicMock(return_value=False)

        with patch("tap_zoho_crm.sync.STREAMS", {"currencies": MagicMock(return_value=parent_stream_mock)}):
            with patch("tap_zoho_crm.sync.build_dynamic_stream", return_value=child_stream_mock):
                client = MagicMock()
                sync(client, {}, mock_catalog, {})

        # The parent should have been synced (added and processed)
        parent_stream_mock.sync.assert_called_once()
