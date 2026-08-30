import unittest
from unittest.mock import patch, MagicMock
from singer.catalog import Catalog

from tap_zoho_crm.discover import discover, _apply_access_checks, _prune_inaccessible_children
from tap_zoho_crm.exceptions import ZohoCRMForbiddenError
from tap_zoho_crm.streams import STREAMS


def _make_stream_cls(accessible=True, parent=""):
    """Helper: return a minimal stream class whose instance.check_access() returns `accessible`."""
    class _MockStreamCls:
        pass
    _MockStreamCls.parent = parent

    def __init__(self, client=None):
        pass

    def check_access(self):
        return accessible

    _MockStreamCls.__init__ = __init__
    _MockStreamCls.check_access = check_access
    return _MockStreamCls


class TestApplyAccessChecks(unittest.TestCase):
    """Tests for _apply_access_checks()."""

    def _make_schemas_and_metadata(self, stream_names=None):
        names = stream_names or list(STREAMS.keys())
        schemas = {name: {"type": "object", "properties": {}} for name in names}
        field_metadata = {name: [] for name in names}
        return schemas, field_metadata

    def test_all_streams_accessible_leaves_catalog_unchanged(self):
        """When all streams are accessible, schemas and field_metadata are unchanged."""
        client = MagicMock()
        all_names = list(STREAMS.keys())
        schemas, field_metadata = self._make_schemas_and_metadata(all_names)

        mock_streams = {name: _make_stream_cls(accessible=True) for name in all_names}

        with patch("tap_zoho_crm.discover.STREAMS", mock_streams):
            _apply_access_checks(client, schemas, field_metadata)

        self.assertEqual(set(schemas.keys()), set(all_names))
        self.assertEqual(set(field_metadata.keys()), set(all_names))

    def test_inaccessible_stream_removed_from_schemas(self):
        """A stream returning False from check_access is removed from schemas and field_metadata."""
        client = MagicMock()
        all_names = list(STREAMS.keys())
        schemas, field_metadata = self._make_schemas_and_metadata(all_names)

        inaccessible_name = all_names[0]
        accessible_names = all_names[1:]

        mock_streams = {
            name: _make_stream_cls(accessible=(name != inaccessible_name))
            for name in all_names
        }

        with patch("tap_zoho_crm.discover.STREAMS", mock_streams):
            _apply_access_checks(client, schemas, field_metadata)

        self.assertNotIn(inaccessible_name, schemas)
        self.assertNotIn(inaccessible_name, field_metadata)
        for name in accessible_names:
            self.assertIn(name, schemas)

    def test_all_parent_streams_inaccessible_raises_forbidden_error(self):
        """Raises ZohoCRMForbiddenError when no parent streams are accessible."""
        client = MagicMock()
        all_names = list(STREAMS.keys())
        schemas, field_metadata = self._make_schemas_and_metadata(all_names)

        mock_streams = {name: _make_stream_cls(accessible=False) for name in all_names}

        with patch("tap_zoho_crm.discover.STREAMS", mock_streams):
            with self.assertRaises(ZohoCRMForbiddenError):
                _apply_access_checks(client, schemas, field_metadata)

    def test_partial_inaccessibility_logs_warning_without_raising(self):
        """Logs a warning but does not raise when only some streams are inaccessible."""
        client = MagicMock()
        all_names = list(STREAMS.keys())
        schemas, field_metadata = self._make_schemas_and_metadata(all_names)

        inaccessible_name = all_names[0]
        mock_streams = {
            name: _make_stream_cls(accessible=(name != inaccessible_name))
            for name in all_names
        }

        with patch("tap_zoho_crm.discover.STREAMS", mock_streams):
            with patch("tap_zoho_crm.discover.LOGGER") as mock_logger:
                _apply_access_checks(client, schemas, field_metadata)
                mock_logger.warning.assert_called_once()
                warning_msg = mock_logger.warning.call_args[0][0]
                self.assertIn("Unauthorized streams excluded from catalog", warning_msg)

        self.assertNotIn(inaccessible_name, schemas)


class TestPruneInaccessibleChildren(unittest.TestCase):
    """Tests for _prune_inaccessible_children()."""

    def test_child_removed_when_parent_absent(self):
        """Child stream is removed from catalog when its parent has already been excluded."""
        schemas = {"child_stream": {}, "other_stream": {}}
        field_metadata = {"child_stream": [], "other_stream": []}

        mock_streams = {
            "child_stream": _make_stream_cls(parent="parent_stream"),
            "other_stream": _make_stream_cls(parent=""),
        }

        with patch("tap_zoho_crm.discover.STREAMS", mock_streams):
            with patch("tap_zoho_crm.discover.LOGGER") as mock_logger:
                _prune_inaccessible_children(schemas, field_metadata)
                mock_logger.warning.assert_called_once()

        self.assertNotIn("child_stream", schemas)
        self.assertNotIn("child_stream", field_metadata)
        self.assertIn("other_stream", schemas)

    def test_child_retained_when_parent_present(self):
        """Child stream is not removed when its parent is present in schemas."""
        schemas = {"parent_stream": {}, "child_stream": {}}
        field_metadata = {"parent_stream": [], "child_stream": []}

        mock_streams = {
            "parent_stream": _make_stream_cls(parent=""),
            "child_stream": _make_stream_cls(parent="parent_stream"),
        }

        with patch("tap_zoho_crm.discover.STREAMS", mock_streams):
            _prune_inaccessible_children(schemas, field_metadata)

        self.assertIn("child_stream", schemas)
        self.assertIn("parent_stream", schemas)

    def test_no_children_no_changes(self):
        """When no streams have a parent, schemas remain unchanged."""
        all_names = list(STREAMS.keys())
        schemas = {name: {} for name in all_names}
        field_metadata = {name: [] for name in all_names}

        # All real Zoho CRM streams have parent="" (no parent)
        _prune_inaccessible_children(schemas, field_metadata)

        self.assertEqual(set(schemas.keys()), set(all_names))


class TestDiscover(unittest.TestCase):
    """Tests for discover()."""

    def _make_mock_stream_entry(self, name):
        entry = MagicMock()
        entry.stream = name
        entry.tap_stream_id = name
        return entry

    @patch("tap_zoho_crm.discover._apply_access_checks")
    @patch("tap_zoho_crm.discover.get_dynamic_schema")
    @patch("tap_zoho_crm.discover.get_static_schemas")
    def test_discover_returns_catalog(self, mock_static, mock_dynamic, mock_access_checks):
        """discover() returns a Catalog instance containing all streams."""
        client = MagicMock()

        mock_static.return_value = (
            {"currencies": {"type": "object", "properties": {"id": {"type": "string"}}}},
            {"currencies": [{"breadcrumb": [], "metadata": {"table-key-properties": ["id"]}}]},
        )
        mock_dynamic.return_value = ({}, {})
        mock_access_checks.return_value = None  # mutates in place, nothing to remove

        catalog = discover(client)

        self.assertIsInstance(catalog, Catalog)
        self.assertEqual(len(catalog.streams), 1)
        self.assertEqual(catalog.streams[0].tap_stream_id, "currencies")

    @patch("tap_zoho_crm.discover._apply_access_checks")
    @patch("tap_zoho_crm.discover.get_dynamic_schema")
    @patch("tap_zoho_crm.discover.get_static_schemas")
    def test_discover_calls_access_checks(self, mock_static, mock_dynamic, mock_access_checks):
        """discover() calls _apply_access_checks with the client and merged schemas."""
        client = MagicMock()
        mock_static.return_value = ({"currencies": {}}, {"currencies": []})
        mock_dynamic.return_value = ({"leads": {}}, {"leads": []})
        mock_access_checks.return_value = None

        discover(client)

        mock_access_checks.assert_called_once()
        call_args = mock_access_checks.call_args[0]
        self.assertEqual(call_args[0], client)
        # Both static and dynamic schemas are merged before the check
        self.assertIn("currencies", call_args[1])
        self.assertIn("leads", call_args[1])

    @patch("tap_zoho_crm.discover._apply_access_checks")
    @patch("tap_zoho_crm.discover.get_dynamic_schema")
    @patch("tap_zoho_crm.discover.get_static_schemas")
    def test_discover_excludes_streams_removed_by_access_check(
        self, mock_static, mock_dynamic, mock_access_checks
    ):
        """Streams removed from schemas by _apply_access_checks are absent from the catalog."""
        client = MagicMock()
        mock_static.return_value = (
            {
                "currencies": {"type": "object", "properties": {"id": {"type": "string"}}},
                "users": {"type": "object", "properties": {"id": {"type": "string"}}},
            },
            {
                "currencies": [{"breadcrumb": [], "metadata": {"table-key-properties": ["id"]}}],
                "users": [{"breadcrumb": [], "metadata": {"table-key-properties": ["id"]}}],
            },
        )
        mock_dynamic.return_value = ({}, {})

        def remove_currencies(client_arg, schemas, field_metadata):
            schemas.pop("currencies", None)
            field_metadata.pop("currencies", None)

        mock_access_checks.side_effect = remove_currencies

        catalog = discover(client)

        stream_ids = [s.tap_stream_id for s in catalog.streams]
        self.assertNotIn("currencies", stream_ids)
        self.assertIn("users", stream_ids)


class TestCheckAccess(unittest.TestCase):
    """Tests for BaseStream.check_access()."""

    def _make_stream(self, parent=""):
        from tap_zoho_crm.streams.currencies import Currencies
        stream = Currencies.__new__(Currencies)
        stream.client = MagicMock()
        stream.parent = parent
        stream.url_endpoint = ""
        stream.path = "org/currencies"
        stream.http_method = "GET"
        stream.params = {}
        stream.headers = {"Accept": "application/json"}
        stream.data_payload = {}
        return stream

    def test_returns_true_when_request_succeeds(self):
        stream = self._make_stream()
        stream.client.make_request.return_value = {}

        self.assertTrue(stream.check_access())

    def test_returns_false_on_forbidden_error(self):
        stream = self._make_stream()
        stream.client.make_request.side_effect = ZohoCRMForbiddenError("403")

        self.assertFalse(stream.check_access())

    def test_child_stream_always_returns_true(self):
        """Child streams bypass the access check and always return True."""
        stream = self._make_stream(parent="parent_stream")
        # make_request should never be called for child streams
        stream.client.make_request.side_effect = ZohoCRMForbiddenError("403")

        self.assertTrue(stream.check_access())
        stream.client.make_request.assert_not_called()

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


class TestDiscoverCatalogDetails(unittest.TestCase):

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
