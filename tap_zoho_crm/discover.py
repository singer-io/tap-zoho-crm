from typing import Dict
import singer
from singer import metadata
from singer.catalog import Catalog, CatalogEntry, Schema
from tap_zoho_crm.schema import get_static_schemas, get_dynamic_schema
from tap_zoho_crm.client import Client

LOGGER = singer.get_logger()


def discover(client: Client) -> Catalog:
    """
    Run the discovery mode, prepare the catalog file and return the catalog.
    """
    static_schemas, static_field_metadata = get_static_schemas()
    dynamic_schemas, dynamic_field_metadata = get_dynamic_schema(client)

    schemas = static_schemas | dynamic_schemas
    field_metadata = static_field_metadata | dynamic_field_metadata

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

