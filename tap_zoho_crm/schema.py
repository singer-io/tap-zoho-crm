import os
import json
import singer
from typing import Dict, Tuple, Optional, Any, Mapping, List
from singer import (
    metrics,
    metadata
)

from tap_zoho_crm.streams import STREAMS
from tap_zoho_crm.client import Client

LOGGER = singer.get_logger()
PK_OVERRIDES = {}
FORCED_FULL_TABLE = {}
REPLICATION_KEY_CANDIDATES = ["Modified_Time", "CreatedDate"]
# List of Zoho CRM modules which are not present in metadata module list but still
# have field metadata available.
FIELD_METADATA_ONLY_MODULES = []
DISPLAY_TYPE_HIDDEN = 3


def get_abs_path(path: str) -> str:
    """
    Get the absolute path for the schema files.
    """
    return os.path.join(os.path.dirname(os.path.realpath(__file__)), path)


def load_schema_references() -> Dict:
    """
    Load the schema files from the schema folder and return the schema references.
    """
    shared_schema_path = get_abs_path("schemas/shared")

    shared_file_names = []
    if os.path.exists(shared_schema_path):
        shared_file_names = [
            f
            for f in os.listdir(shared_schema_path)
            if os.path.isfile(os.path.join(shared_schema_path, f))
        ]

    refs = {}
    for shared_schema_file in shared_file_names:
        with open(os.path.join(shared_schema_path, shared_schema_file)) as data_file:
            refs["shared/" + shared_schema_file] = json.load(data_file)

    return refs


def get_static_schemas() -> Tuple[Dict, Dict]:
    """
    Load the schema references, prepare metadata for each streams from a
    static 'stream's.json' file and return schema and metadata for the catalog.
    """
    schemas = {}
    field_metadata = {}

    refs = load_schema_references()
    for stream_name, stream_obj in STREAMS.items():
        schema_path = get_abs_path("schemas/{}.json".format(stream_name))
        with open(schema_path) as file:
            schema = json.load(file)

        schemas[stream_name] = schema
        schema = singer.resolve_schema_references(schema, refs)

        mdata = metadata.new()
        mdata = metadata.get_standard_metadata(
            schema=schema,
            key_properties=getattr(stream_obj, "key_properties"),
            valid_replication_keys=(getattr(stream_obj, "replication_keys") or []),
            replication_method=getattr(stream_obj, "replication_method"),
        )
        mdata = metadata.to_map(mdata)

        automatic_keys = getattr(stream_obj, "replication_keys") or []
        for field_name in schema.get("properties", {}).keys():
            if field_name in automatic_keys:
                mdata = metadata.write(
                    mdata, ("properties", field_name), "inclusion", "automatic"
                )

        parent_tap_stream_id = getattr(stream_obj, "parent", None)
        if parent_tap_stream_id:
            mdata = metadata.write(mdata, (), 'parent-tap-stream-id', parent_tap_stream_id)

        mdata = metadata.to_list(mdata)
        field_metadata[stream_name] = mdata

    return schemas, field_metadata


def should_include_field(field: Dict, expected_pk_field: str) -> bool:
    """
    Determine whether a Zoho CRM field should be included in the schema.
    These criteria are based on Zoho CRM field properties to ensure only relevant,
    user-visible, and non-virtual fields are included in the schema.
    """
    api_name = field.get("api_name")

    if api_name == expected_pk_field:
        return True

    return (
        api_name is not None
        and field.get("visible", False)
        and field.get("view_type", {}).get("view", False)
        and not field.get("virtual_field", False)
        and field.get("display_type", -1) != DISPLAY_TYPE_HIDDEN
    )


def get_replication_and_primary_key(
        module: str,
        fields: List[dict]
    ) -> Tuple[Optional[str], Optional[str]]:
    """
    Determine the appropriate replication key and primary key for a module.
    """
    field_lookup = {}
    for field in fields:
        api_name = field.get('api_name')
        if not api_name:
            continue

        key = api_name.lower()
        if key in field_lookup:
            LOGGER.warning(
                f"Duplicate api_name detected when lowercased: '{api_name}' "
                f"(collides with '{field_lookup[key]}') in module '{module}'."
            )
        field_lookup[key] = api_name

    replication_key = None
    if module not in FORCED_FULL_TABLE:
        for candidate in REPLICATION_KEY_CANDIDATES:
            candidate = candidate.lower()
            if candidate in field_lookup:
                replication_key = field_lookup.get(candidate)
                break

    primary_key = PK_OVERRIDES.get(module)
    if not primary_key:
        if "id" in field_lookup:
            primary_key = "id"
        elif "sequence_number" in field_lookup:
            primary_key = field_lookup.get("sequence_number")
        else:
            primary_key = None

    return replication_key, primary_key


def field_to_property_schema(field: Dict) -> Dict:
    """
    Convert a Zoho CRM field metadata dict to a Singer-compatible property schema.
    This function maps Zoho CRM field metadata (primarily `data_type` and `json_type`)
    to a JSON schema property definition compatible with Singer. The mapping logic
    covers a variety of Zoho CRM field types and their expected JSON representations.

    Allowing additionalProperties is required to support the flexible data model of Zoho CRM.

    Parameters:
        field (Dict): A dictionary containing Zoho CRM field metadata, including
            at least the keys "data_type" and "json_type".

    Returns:
        Dict: A JSON schema property definition for the field.
    """
    json_type = field.get("json_type")
    data_type = field.get("data_type")

    string_types = {"picklist", "email", "website", "text", "textarea", "phone", "formula", "profilelookup"}
    integer_types = {"integer", "long", "bigint"}
    number_types = {"double", "decimal"}
    datetime_types = {"datetime", "date"}

    if data_type == "multiselectpicklist":
        return {"type": ["null", "array"], "items": {"type": ["null", "string"]}}

    if data_type == "text" and json_type == "jsonarray":
        return {"type": ["null", "array"], "items": {"type": ["null", "string"]}}

    if data_type in {"multireminder", "subform"} or json_type == "jsonarray":
        return {"type": ["null", "array"], "items": {"type": ["null", "object"], "additionalProperties": True}}

    if data_type in {"lookup", "ownerlookup", "userlookup", "profilelookup"}:
        if json_type == "jsonobject":
            return {"type": ["null", "object"], "additionalProperties": True}
        return {"type": ["null", "string"]}

    if data_type == "attachment":
        return {"type": ["null", "array"], "items": {"type": ["null", "object"], "additionalProperties": True}}

    if data_type == "currency":
        if json_type == "jsonobject":
            return {"type": ["null", "object"], "additionalProperties": True}
        return {"type": ["null", "number"]}

    if data_type == "boolean":
        return {"type": ["null", "boolean"]}

    if data_type in datetime_types:
        return {"type": ["null", "string"], "format": "date-time"}

    if data_type in integer_types:
        return {"type": ["null", "integer"]}

    if data_type in number_types:
        return {"type": ["null", "number"]}

    if data_type in string_types:
        return {"type": ["null", "string"]}

    return {"type": ["null", "string"]}


def get_dynamic_schema(client: Client) -> Tuple[Dict, Dict]:
    """
    Dynamically generate or fetch stream schemas and associated metadata
    and return schema and metadata for the catalog.
    """
    LOGGER.info("Fetching dynamic schema from Zoho CRM.")
    schemas = {}
    field_metadata = {}
    refs = load_schema_references()
    available_modules = get_dynamic_metadata(client)

    available_modules = [
        module.get("api_name") for module in available_modules.get("modules", [])
        if module.get("viewable") and module.get("api_supported")]

    available_modules.extend(FIELD_METADATA_ONLY_MODULES)

    for module in available_modules:
        module_metadata = get_dynamic_metadata(client, module=module)
        module_metadata = module_metadata.get("fields", [])
        if not module_metadata:
            LOGGER.info(f"Skipping module {module}: No field metadata available.")
            continue

        properties = dict()
        replication_key, pk_field = get_replication_and_primary_key(module, module_metadata)

        if not pk_field:
            LOGGER.info(f"Skipping module {module}: No primary key field found.")
            continue

        for field in module_metadata:
            if should_include_field(field, pk_field):
                field_name = field.get("api_name")
                property_schema = field_to_property_schema(field)
                properties[field_name] = property_schema

        if "id" not in properties:
            properties["id"] = {"type": ["null", "string"]}
            pk_field = "id"

        module_schema = {
            "type": "object",
            "properties": properties
        }
        schemas[module] = module_schema
        module_schema = singer.resolve_schema_references(module_schema, refs)

        mdata = metadata.new()
        mdata = metadata.get_standard_metadata(
            schema=module_schema,
            key_properties=[pk_field],
            valid_replication_keys=[replication_key] if replication_key else [],
            replication_method="INCREMENTAL" if replication_key else "FULL_TABLE"
        )
        mdata = metadata.to_map(mdata)

        if replication_key:
            mdata = metadata.write(
                mdata, ('properties', replication_key), 'inclusion', 'automatic')

        mdata = metadata.write(mdata, (), 'module-path', module)
        field_metadata[module] = metadata.to_list(mdata)

    return schemas, field_metadata


def get_dynamic_metadata(client: Client, module: Optional[str] = None) -> Optional[Mapping[Any, Any]]:
    """
    Fetch dynamic metadata from the Zoho CRM API.
    """
    params = {}
    if module is None:
        path = "settings/modules"
        endpoint_tag = "modules"
    else:
        path = f"settings/fields"
        endpoint_tag = module
        params = {"module": module}

    endpoint = f"{client.base_url}/{path}"
    with metrics.http_request_timer("describe") as timer:
        timer.tags['endpoint'] = endpoint_tag
        response = client.make_request('GET', endpoint, params=params)

    return response

