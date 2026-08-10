import json
import unittest
from unittest.mock import patch, MagicMock, mock_open
from tap_zoho_crm.schema import (
    load_schema_references,
    get_static_schemas,
    get_replication_and_primary_key,
    field_to_property_schema,
    get_dynamic_schema,
    get_dynamic_metadata,
)


class TestLoadSchemaReferences(unittest.TestCase):

    def test_load_schema_references_no_shared_dir(self):
        """Returns empty dict when schemas/shared directory does not exist."""
        with patch('tap_zoho_crm.schema.os.path.exists', return_value=False):
            result = load_schema_references()
        self.assertEqual(result, {})

    def test_load_schema_references_with_shared_files(self):
        """Returns refs dict when schemas/shared directory exists with JSON files."""
        schema_data = {"type": "object"}
        m = mock_open(read_data=json.dumps(schema_data))

        with patch('tap_zoho_crm.schema.os.path.exists', return_value=True), \
             patch('tap_zoho_crm.schema.os.listdir', return_value=['shared_schema.json']), \
             patch('tap_zoho_crm.schema.os.path.isfile', return_value=True), \
             patch('builtins.open', m):
            result = load_schema_references()

        self.assertIn('shared/shared_schema.json', result)
        self.assertEqual(result['shared/shared_schema.json'], schema_data)

    def test_load_schema_references_skips_non_files(self):
        """Skips non-file entries (e.g. sub-directories) in shared dir."""
        with patch('tap_zoho_crm.schema.os.path.exists', return_value=True), \
             patch('tap_zoho_crm.schema.os.listdir', return_value=['subdir']), \
             patch('tap_zoho_crm.schema.os.path.isfile', return_value=False):
            result = load_schema_references()

        self.assertEqual(result, {})


class TestGetStaticSchemas(unittest.TestCase):

    def test_get_static_schemas_returns_schemas_and_metadata(self):
        """Verify get_static_schemas returns schemas and field metadata for all static streams."""
        schemas, field_metadata = get_static_schemas()

        self.assertIsInstance(schemas, dict)
        self.assertIsInstance(field_metadata, dict)
        self.assertGreater(len(schemas), 0)
        self.assertEqual(set(schemas.keys()), set(field_metadata.keys()))

    def test_get_static_schemas_each_stream_has_key_properties(self):
        """Each stream's metadata should contain table-key-properties."""
        from singer import metadata as singer_metadata
        _, field_metadata = get_static_schemas()

        for stream_name, mdata in field_metadata.items():
            mdata_map = singer_metadata.to_map(mdata)
            key_props = mdata_map.get((), {}).get('table-key-properties')
            self.assertIsNotNone(
                key_props,
                msg=f"Stream '{stream_name}' is missing table-key-properties"
            )

    def test_get_static_schemas_includes_replication_method(self):
        """Each stream's metadata should contain forced-replication-method."""
        from singer import metadata as singer_metadata
        _, field_metadata = get_static_schemas()

        for stream_name, mdata in field_metadata.items():
            mdata_map = singer_metadata.to_map(mdata)
            rep_method = mdata_map.get((), {}).get('forced-replication-method')
            self.assertIsNotNone(
                rep_method,
                msg=f"Stream '{stream_name}' is missing forced-replication-method"
            )


class TestGetReplicationAndPrimaryKey(unittest.TestCase):

    def test_duplicate_api_name_warning_is_logged(self):
        """When two fields have the same lowercased api_name, a warning is logged."""
        fields = [
            {"api_name": "Modified_Time"},
            {"api_name": "modified_time"},   # duplicate after lower()
            {"api_name": "id"},
        ]
        with patch('tap_zoho_crm.schema.LOGGER') as mock_logger:
            replication_key, pk = get_replication_and_primary_key("TestModule", fields)

        mock_logger.warning.assert_called_once()
        warning_msg = str(mock_logger.warning.call_args)
        self.assertIn("modified_time", warning_msg.lower())

    def test_replication_key_found_via_candidate_lookup(self):
        """Replication key is resolved from REPLICATION_KEY_CANDIDATES lookup."""
        fields = [
            {"api_name": "Modified_Time"},
            {"api_name": "id"},
        ]
        replication_key, pk = get_replication_and_primary_key("TestModule", fields)
        self.assertEqual(replication_key, "Modified_Time")

    def test_sequence_number_used_as_primary_key_when_no_id(self):
        """Falls back to sequence_number when no 'id' field exists."""
        fields = [
            {"api_name": "Sequence_Number"},
            {"api_name": "Name"},
        ]
        _, pk = get_replication_and_primary_key("TestModule", fields)
        self.assertEqual(pk, "Sequence_Number")

    def test_no_primary_key_when_no_id_or_sequence_number(self):
        """Returns None primary key when neither id nor sequence_number exists."""
        fields = [{"api_name": "Name"}]
        _, pk = get_replication_and_primary_key("TestModule", fields)
        self.assertIsNone(pk)

    def test_field_with_no_api_name_is_skipped(self):
        """Fields with missing api_name are skipped silently."""
        fields = [
            {"api_name": None},
            {"api_name": ""},
            {"api_name": "id"},
        ]
        replication_key, pk = get_replication_and_primary_key("TestModule", fields)
        self.assertEqual(pk, "id")


class TestFieldToPropertySchema(unittest.TestCase):

    def test_multiselectpicklist(self):
        result = field_to_property_schema({"data_type": "multiselectpicklist"})
        self.assertEqual(result["type"], ["null", "array"])
        self.assertEqual(result["items"]["type"], ["null", "string"])

    def test_text_with_jsonarray(self):
        result = field_to_property_schema({"data_type": "text", "json_type": "jsonarray"})
        self.assertEqual(result["type"], ["null", "array"])

    def test_multireminder_returns_array_of_objects(self):
        result = field_to_property_schema({"data_type": "multireminder"})
        self.assertEqual(result["type"], ["null", "array"])
        self.assertTrue(result["items"].get("additionalProperties"))

    def test_jsonarray_json_type_returns_array_of_objects(self):
        result = field_to_property_schema({"data_type": "other", "json_type": "jsonarray"})
        self.assertEqual(result["type"], ["null", "array"])

    def test_lookup_with_jsonobject_returns_object(self):
        """lookup + jsonobject → object type (previously uncovered branch)."""
        result = field_to_property_schema({"data_type": "lookup", "json_type": "jsonobject"})
        self.assertEqual(result["type"], ["null", "object"])
        self.assertTrue(result.get("additionalProperties"))

    def test_lookup_without_jsonobject_returns_string(self):
        result = field_to_property_schema({"data_type": "ownerlookup", "json_type": "string"})
        self.assertEqual(result["type"], ["null", "string"])

    def test_attachment_returns_array_of_objects(self):
        """attachment → array of objects (previously uncovered branch)."""
        result = field_to_property_schema({"data_type": "attachment"})
        self.assertEqual(result["type"], ["null", "array"])
        self.assertTrue(result["items"].get("additionalProperties"))

    def test_currency_with_jsonobject_returns_object(self):
        """currency + jsonobject → object type (previously uncovered branch)."""
        result = field_to_property_schema({"data_type": "currency", "json_type": "jsonobject"})
        self.assertEqual(result["type"], ["null", "object"])

    def test_currency_without_jsonobject_returns_number(self):
        result = field_to_property_schema({"data_type": "currency", "json_type": "double"})
        self.assertEqual(result["type"], ["null", "number"])

    def test_boolean_type(self):
        result = field_to_property_schema({"data_type": "boolean"})
        self.assertEqual(result["type"], ["null", "boolean"])

    def test_datetime_type(self):
        result = field_to_property_schema({"data_type": "datetime"})
        self.assertEqual(result.get("format"), "date-time")

    def test_integer_type(self):
        result = field_to_property_schema({"data_type": "integer"})
        self.assertEqual(result["type"], ["null", "integer"])

    def test_number_type(self):
        result = field_to_property_schema({"data_type": "double"})
        self.assertEqual(result["type"], ["null", "number"])

    def test_string_picklist(self):
        result = field_to_property_schema({"data_type": "picklist"})
        self.assertEqual(result["type"], ["null", "string"])

    def test_unknown_type_falls_through_to_string(self):
        """Unrecognized data_type falls through to string (previously uncovered branch)."""
        result = field_to_property_schema({"data_type": "unknown_exotic_type"})
        self.assertEqual(result["type"], ["null", "string"])


class TestGetDynamicSchema(unittest.TestCase):

    def _make_client(self, modules_response, fields_response):
        mock_client = MagicMock()
        mock_client.base_url = "https://www.zohoapis.com/crm/v8"
        mock_client.make_request.side_effect = [modules_response, fields_response]
        return mock_client

    @patch('tap_zoho_crm.schema.metrics.http_request_timer')
    def test_get_dynamic_schema_basic(self, mock_timer):
        """Test get_dynamic_schema builds schema and metadata for available modules."""
        mock_timer.return_value.__enter__ = MagicMock(return_value=MagicMock())
        mock_timer.return_value.__exit__ = MagicMock(return_value=False)

        modules_resp = {
            "modules": [
                {"api_name": "Contacts", "viewable": True, "api_supported": True}
            ]
        }
        fields_resp = {
            "fields": [
                {
                    "api_name": "id",
                    "visible": True,
                    "view_type": {"view": True},
                    "virtual_field": False,
                    "display_type": 1,
                    "data_type": "text",
                    "json_type": "string"
                },
                {
                    "api_name": "Modified_Time",
                    "visible": True,
                    "view_type": {"view": True},
                    "virtual_field": False,
                    "display_type": 1,
                    "data_type": "datetime",
                    "json_type": "string"
                }
            ]
        }

        mock_client = MagicMock()
        mock_client.base_url = "https://www.zohoapis.com/crm/v8"
        mock_client.make_request.side_effect = [modules_resp, fields_resp]

        schemas, field_metadata = get_dynamic_schema(mock_client)

        self.assertIn("Contacts", schemas)
        self.assertIn("Contacts", field_metadata)

    @patch('tap_zoho_crm.schema.metrics.http_request_timer')
    def test_get_dynamic_schema_skips_module_with_no_fields(self, mock_timer):
        """Modules with no field metadata are skipped."""
        mock_timer.return_value.__enter__ = MagicMock(return_value=MagicMock())
        mock_timer.return_value.__exit__ = MagicMock(return_value=False)

        modules_resp = {
            "modules": [
                {"api_name": "EmptyModule", "viewable": True, "api_supported": True}
            ]
        }
        fields_resp = {"fields": []}

        mock_client = MagicMock()
        mock_client.base_url = "https://www.zohoapis.com/crm/v8"
        mock_client.make_request.side_effect = [modules_resp, fields_resp]

        schemas, _ = get_dynamic_schema(mock_client)

        self.assertNotIn("EmptyModule", schemas)

    @patch('tap_zoho_crm.schema.metrics.http_request_timer')
    def test_get_dynamic_schema_skips_module_with_no_pk(self, mock_timer):
        """Modules with no identifiable primary key are skipped."""
        mock_timer.return_value.__enter__ = MagicMock(return_value=MagicMock())
        mock_timer.return_value.__exit__ = MagicMock(return_value=False)

        modules_resp = {
            "modules": [
                {"api_name": "NoPkModule", "viewable": True, "api_supported": True}
            ]
        }
        fields_resp = {
            "fields": [
                {
                    "api_name": "Name",
                    "visible": True,
                    "view_type": {"view": True},
                    "virtual_field": False,
                    "display_type": 1,
                    "data_type": "text",
                    "json_type": "string"
                }
            ]
        }

        mock_client = MagicMock()
        mock_client.base_url = "https://www.zohoapis.com/crm/v8"
        mock_client.make_request.side_effect = [modules_resp, fields_resp]

        schemas, _ = get_dynamic_schema(mock_client)

        self.assertNotIn("NoPkModule", schemas)

    @patch('tap_zoho_crm.schema.metrics.http_request_timer')
    def test_get_dynamic_schema_adds_id_when_missing_from_properties(self, mock_timer):
        """If 'id' not included in visible fields, it is added manually."""
        mock_timer.return_value.__enter__ = MagicMock(return_value=MagicMock())
        mock_timer.return_value.__exit__ = MagicMock(return_value=False)

        modules_resp = {
            "modules": [
                {"api_name": "TestMod", "viewable": True, "api_supported": True}
            ]
        }
        # Only 'id' field but not visible (so should_include_field returns True because it's pk)
        fields_resp = {
            "fields": [
                {
                    "api_name": "id",
                    "visible": False,
                    "view_type": {"view": False},
                    "virtual_field": False,
                    "display_type": 1,
                    "data_type": "text",
                    "json_type": "string"
                }
            ]
        }

        mock_client = MagicMock()
        mock_client.base_url = "https://www.zohoapis.com/crm/v8"
        mock_client.make_request.side_effect = [modules_resp, fields_resp]

        schemas, _ = get_dynamic_schema(mock_client)
        self.assertIn("TestMod", schemas)
        self.assertIn("id", schemas["TestMod"]["properties"])

    @patch('tap_zoho_crm.schema.metrics.http_request_timer')
    def test_get_dynamic_schema_skips_non_viewable_modules(self, mock_timer):
        """Modules that are not viewable or not api_supported are excluded."""
        mock_timer.return_value.__enter__ = MagicMock(return_value=MagicMock())
        mock_timer.return_value.__exit__ = MagicMock(return_value=False)

        modules_resp = {
            "modules": [
                {"api_name": "HiddenMod", "viewable": False, "api_supported": True},
                {"api_name": "UnsupportedMod", "viewable": True, "api_supported": False},
            ]
        }
        mock_client = MagicMock()
        mock_client.base_url = "https://www.zohoapis.com/crm/v8"
        mock_client.make_request.return_value = modules_resp

        schemas, _ = get_dynamic_schema(mock_client)

        self.assertEqual(schemas, {})


class TestGetDynamicMetadata(unittest.TestCase):

    @patch('tap_zoho_crm.schema.metrics.http_request_timer')
    def test_get_dynamic_metadata_modules(self, mock_timer):
        """Fetches modules list when no module name is given."""
        mock_timer_ctx = MagicMock()
        mock_timer.return_value.__enter__ = MagicMock(return_value=mock_timer_ctx)
        mock_timer.return_value.__exit__ = MagicMock(return_value=False)

        mock_client = MagicMock()
        mock_client.base_url = "https://www.zohoapis.com/crm/v8"
        mock_client.make_request.return_value = {"modules": []}

        result = get_dynamic_metadata(mock_client)

        self.assertEqual(result, {"modules": []})
        mock_client.make_request.assert_called_once_with(
            'GET',
            "https://www.zohoapis.com/crm/v8/settings/modules",
            params={}
        )

    @patch('tap_zoho_crm.schema.metrics.http_request_timer')
    def test_get_dynamic_metadata_fields_for_module(self, mock_timer):
        """Fetches field metadata when a module name is provided."""
        mock_timer_ctx = MagicMock()
        mock_timer.return_value.__enter__ = MagicMock(return_value=mock_timer_ctx)
        mock_timer.return_value.__exit__ = MagicMock(return_value=False)

        mock_client = MagicMock()
        mock_client.base_url = "https://www.zohoapis.com/crm/v8"
        mock_client.make_request.return_value = {"fields": []}

        result = get_dynamic_metadata(mock_client, module="Contacts")

        self.assertEqual(result, {"fields": []})
        mock_client.make_request.assert_called_once_with(
            'GET',
            "https://www.zohoapis.com/crm/v8/settings/fields",
            params={"module": "Contacts"}
        )
