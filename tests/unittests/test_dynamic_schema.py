import unittest
from parameterized import parameterized
from tap_zoho_crm.schema import (
    should_include_field,
    get_replication_and_primary_key,
    field_to_property_schema
)


class TestSchemaFunctions(unittest.TestCase):

    def test_should_include_field_true_for_primary(self):
        """
        should_include_field should return True for the primary key field
        even if visibility is False.
        """
        field = {
            "api_name": "my_id",
            "visible": False,
            "view_type": {"view": False},
            "virtual_field": False,
            "display_type": 1
        }
        self.assertTrue(should_include_field(field, expected_pk_field="my_id"))

    @parameterized.expand([
        (
            "visible_and_viewable",
            {
                "api_name": "name",
                "visible": True,
                "view_type": {"view": True},
                "virtual_field": False,
                "display_type": 1
            },
            True
        ),
        (
            "not_visible",
            {
                "api_name": "name",
                "visible": False,
                "view_type": {"view": True},
                "virtual_field": False,
                "display_type": 1
            },
            False
        ),
        (
            "virtual_field",
            {
                "api_name": "name",
                "visible": True,
                "view_type": {"view": True},
                "virtual_field": True,
                "display_type": 1
            },
            False
        ),
        (
            "hidden_display_type",
            {
                "api_name": "name",
                "visible": True,
                "view_type": {"view": True},
                "virtual_field": False,
                "display_type": 3
            },
            False
        ),
    ])
    def test_should_include_field_general(self, name, field, expected):
        """
        should_include_field returns correct inclusion behavior for various field attributes.
        """
        self.assertEqual(should_include_field(field, expected_pk_field="pk"), expected)

    @parameterized.expand([
        ("explicit_rep_key_and_id_pk",
            "ModA", [{"api_name": "Modified_Time"}, {"api_name": "id"}], "Modified_Time", "id"),
        ("only_created_date",
            "ModB", [{"api_name": "CreatedDate"}], "CreatedDate", None),
        ("sequence_number_pk",
            "ModC", [{"api_name": "something_else"}, {"api_name": "Sequence_Number"}], None, "Sequence_Number"),
        ("no_replication_or_pk",
            "ModD", [{"api_name": "foo"}], None, None),
    ])
    def test_get_replication_and_primary_key(self, name, module, fields, expected_replication_key, expected_pk_field):
        """
        Tests matching replication and primary key selection logic.
        """
        replication_key, pk = get_replication_and_primary_key(module, fields)
        self.assertEqual(replication_key, expected_replication_key)
        self.assertEqual(pk, expected_pk_field)

    @parameterized.expand([
        ("boolean_type", {"data_type": "boolean"}, {"type": ["null", "boolean"]}),
        ("datetime_string", {"data_type": "datetime", "json_type": "string"}, {"type": ["null", "string"], "format": "date-time"}),
        ("integer_type", {"data_type": "integer", "json_type": "number"}, {"type": ["null", "integer"]}),
        ("decimal_type", {"data_type": "decimal", "json_type": "number"}, {"type": ["null", "number"]}),
        ("text_jsonarray", {"data_type": "text", "json_type": "jsonarray"}, {"type": ["null", "array"], "items": {"type": ["null", "string"]}}),
        ("multiselectpicklist", {"data_type": "multiselectpicklist"}, {"type": ["null", "array"], "items": {"type": ["null", "string"]}}),
        ("lookup_jsonobject", {"data_type": "lookup", "json_type": "jsonobject"}, {"type": ["null", "object"], "additionalProperties": True}),
        ("currency_jsonobject", {"data_type": "currency", "json_type": "jsonobject"}, {"type": ["null", "object"], "additionalProperties": True}),
        ("currency_number", {"data_type": "currency", "json_type": "number"}, {"type": ["null", "number"]}),
        ("fallback_unknown", {"data_type": "unknown", "json_type": "unknown"}, {"type": ["null", "string"]}),
    ])
    def test_field_to_property_schema(self, name, field, expected_schema):
        """
        Tests conversion from Zoho CRM field metadata to Singer property schema.
        """
        result_schema = field_to_property_schema(field)
        self.assertEqual(result_schema, expected_schema)

