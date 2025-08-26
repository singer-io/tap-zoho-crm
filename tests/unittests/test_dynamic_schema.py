import pytest
from tap_zoho_crm.schema import (
    should_include_field,
    get_replication_and_primary_key,
    field_to_property_schema
)

def test_should_include_field_true_for_primary():
    """
    should_include_field should return True for the primary key field even if visibility is False.
    """
    field = {
        "api_name": "my_id",
        "visible": False,
        "view_type": {"view": False},
        "virtual_field": False,
        "display_type": 1
    }
    assert should_include_field(field, expected_pk_field="my_id") is True

@pytest.mark.parametrize(
    "field, expected",
    [
        (
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
            {
                "api_name": "name",
                "visible": True,
                "view_type": {"view": True},
                "virtual_field": False,
                "display_type": 3
            },
            False
        ),
    ],
    ids=[
        "visible & viewable",
        "not visible",
        "virtual field",
        "hidden display_type"
    ]
)
def test_should_include_field_general(field, expected):
    """
    should_include_field returns correct inclusion behavior for various field attributes.
    """
    assert should_include_field(field, expected_pk_field="pk") is expected

@pytest.mark.parametrize(
    "module, fields, expected_replication_key, expected_pk_field",
    [
        ("ModA", [{"api_name": "Modified_Time"}, {"api_name": "id"}], "Modified_Time", "id"),
        ("ModB", [{"api_name": "CreatedDate"}], "CreatedDate", None),
        ("ModC", [{"api_name": "something_else"}, {"api_name": "Sequence_Number"}], None, "Sequence_Number"),
        ("ModD", [{"api_name": "foo"}], None, None),
    ],
    ids=["explicit rep key + id pk", "only created", "seq_number pk", "none"]
)
def test_get_replication_and_primary_key(module, fields, expected_replication_key, expected_pk_field):
    """
    Tests matching replication and primary key selection logic.
    """
    replication_key, pk = get_replication_and_primary_key(module, fields)
    assert replication_key == expected_replication_key
    assert pk == expected_pk_field

@pytest.mark.parametrize(
    "field, expected_schema",
    [
        (
            {"data_type": "boolean"},
            {"type": ["null", "boolean"]}
        ),
        (
            {"data_type": "datetime", "json_type": "string"},
            {"type": ["null", "string"], "format": "date-time"}
        ),
        (
            {"data_type": "integer", "json_type": "number"},
            {"type": ["null", "integer"]}
        ),
        (
            {"data_type": "decimal", "json_type": "number"},
            {"type": ["null", "number"]}
        ),
        (
            {"data_type": "text", "json_type": "jsonarray"},
            {"type": ["null", "array"], "items": {"type": ["null", "string"]}}
        ),
        (
            {"data_type": "multiselectpicklist"},
            {"type": ["null", "array"], "items": {"type": ["null", "string"]}}
        ),
        (
            {"data_type": "lookup", "json_type": "jsonobject"},
            {"type": ["null", "object"], "additionalProperties": True}
        ),
        (
            {"data_type": "currency", "json_type": "jsonobject"},
            {"type": ["null", "object"], "additionalProperties": True}
        ),
        (
            {"data_type": "currency", "json_type": "number"},
            {"type": ["null", "number"]}
        ),
        (
            {"data_type": "unknown", "json_type": "unknown"},
            {"type": ["null", "string"]}
        ),
    ],
    ids=[
        "boolean",
        "datetime",
        "integer",
        "decimal",
        "text jsonarray",
        "multiselect",
        "lookup object",
        "currency object",
        "currency number",
        "fallback string"
    ]
)
def test_field_to_property_schema(field, expected_schema):
    """
    Tests conversion from Zoho CRM field metadata to Singer property schema.
    """
    result_schema = field_to_property_schema(field)
    assert result_schema == expected_schema
