from typing import Dict
import singer
from singer import metadata
from singer.catalog import Catalog, CatalogEntry, Schema
from tap_zoho_crm.schema import get_static_schemas, get_dynamic_schema
from tap_zoho_crm.client import Client
from tap_zoho_crm.streams import STREAMS
from tap_zoho_crm.exceptions import ZohoCRMForbiddenError

LOGGER = singer.get_logger()


def _apply_access_checks(client: Client, schemas: dict, field_metadata: dict) -> None:
    """
    Probe each stream for read access and remove inaccessible streams
    (and their children) from schemas and field_metadata in place.
    Probes both static (STREAMS) and dynamic CRM module streams.
    Note: check_access() always returns True for child streams, so this loop
    effectively identifies only inaccessible parent streams by design.
    Child stream removal is handled separately by _prune_inaccessible_children().
    Raises ZohoCRMForbiddenError if no parent streams are accessible.
    """
    inaccessible_streams = [
        stream_name
        for stream_name, stream_obj in STREAMS.items()
        if stream_name in schemas
        and not stream_obj(client=client).check_access()
    ]

    # Probe dynamic CRM modules (schemas not in STREAMS) for access.
    # These are discovered at runtime and may have module-level permissions.
    dynamic_modules = [
        stream_name
        for stream_name in schemas.keys()
        if stream_name not in STREAMS
    ]
    for module_name in dynamic_modules:
        try:
            response = client.make_request(
                "GET",
                f"{client.base_url}/settings/fields",
                params={"module": module_name}
            )
            # Successful response indicates the module is accessible
        except ZohoCRMForbiddenError as exc:
            LOGGER.warning(
                f"Dynamic module '{module_name}' is not accessible and will be excluded. "
                f"HTTP-Error-Message: '{str(exc)}'"
            )
            inaccessible_streams.append(module_name)

    for stream_name in inaccessible_streams:
        schemas.pop(stream_name, None)
        field_metadata.pop(stream_name, None)

    inaccessible_streams.extend(_prune_inaccessible_children(schemas, field_metadata))

    if not schemas:
        raise ZohoCRMForbiddenError(
            "HTTP-error-code: 403, Error: The credentials do not \
                have 'read' access to any supported streams."
        )
    elif inaccessible_streams:
        LOGGER.warning(
            "Unauthorized streams excluded from catalog: %s",
            ", ".join(inaccessible_streams),
        )


def _prune_inaccessible_children(schemas: dict, field_metadata: dict) -> None:
    """
    Remove child streams from the catalog whose parent stream was excluded.
    Mutates schemas and field_metadata in place.
    """
    to_remove = []
    for name, stream_cls in list(STREAMS.items()):
        if name in schemas and stream_cls.parent and stream_cls.parent not in schemas:
            LOGGER.warning(
                "Stream '%s' excluded from catalog because its \
                    parent stream '%s' is not accessible.",
                name, stream_cls.parent,
            )
            schemas.pop(name, None)
            field_metadata.pop(name, None)
            to_remove.append(name)
    return to_remove


def discover(client: Client) -> Catalog:
    """
    Run the discovery mode, prepare the catalog file and return the catalog.
    Access to each stream is verified using the provided client and streams
    the credentials cannot read are excluded from the returned catalog.
    """
    static_schemas, static_field_metadata = get_static_schemas()
    dynamic_schemas, dynamic_field_metadata = get_dynamic_schema(client)

    schemas = static_schemas | dynamic_schemas
    field_metadata = static_field_metadata | dynamic_field_metadata

    _apply_access_checks(client, schemas, field_metadata)

    catalog = Catalog([])

    for stream_name, schema_dict in schemas.items():
        try:
            schema = Schema.from_dict(schema_dict)
            mdata = field_metadata[stream_name]
        except Exception as err:
            LOGGER.error(err)
            LOGGER.error("stream_name: {}".format(stream_name))
            LOGGER.error("type schema_dict: {}".format(type(schema_dict)))
            raise err

        key_properties = metadata.to_map(mdata).get((), {}).get("table-key-properties")
        stream_name = stream_name.lower()
        catalog.streams.append(
            CatalogEntry(
                stream=stream_name,
                tap_stream_id=stream_name,
                key_properties=key_properties,
                schema=schema,
                metadata=mdata,
            )
        )

    return catalog

