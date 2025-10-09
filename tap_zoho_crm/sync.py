from typing import Dict
import singer
from singer import metadata
from tap_zoho_crm.streams import STREAMS, abstracts
from tap_zoho_crm.client import Client
from tap_zoho_crm.streams.abstracts import IncrementalStream, FullTableStream

LOGGER = singer.get_logger()


def update_currently_syncing(state: Dict, stream_name: str) -> None:
    """
    Update currently_syncing in state and write it
    """
    if not stream_name and singer.get_currently_syncing(state):
        del state["currently_syncing"]
    else:
        singer.set_currently_syncing(state, stream_name)
    singer.write_state(state)


def write_schema(stream, client, streams_to_sync, catalog) -> None:
    """
    Write schema for stream and its children
    """
    if stream.is_selected():
        stream.write_schema()

    for child in stream.children:
        child_obj = STREAMS[child](client, catalog.get_stream(child))
        write_schema(child_obj, client, streams_to_sync, catalog)
        if child in streams_to_sync:

            stream.child_to_sync.append(child_obj)


def build_dynamic_stream(client, catalog_entry: singer.CatalogEntry) -> object:
    """Create a dynamic stream instance based on stream_catalog."""
    catalog_metadata = metadata.to_map(catalog_entry.metadata)

    tap_stream_id = catalog_entry.tap_stream_id
    key_properties = catalog_entry.key_properties
    replication_method = catalog_metadata.get((), {}).get('forced-replication-method')
    replication_keys = catalog_metadata.get((), {}).get('valid-replication-keys')

    class_props = {
        "__module__": abstracts.__name__,
        "tap_stream_id": property(lambda self: tap_stream_id),
        "key_properties": property(lambda self: key_properties),
        "replication_method": property(lambda self: replication_method),
        "replication_keys": property(lambda self: replication_keys),
        "path": tap_stream_id,
        "data_key": "data",
        "is_dynamic": True
    }

    base_class = IncrementalStream if replication_method.upper() == "INCREMENTAL" else FullTableStream

    DynamicStreamClass = type(
        f"Dynamic{tap_stream_id.title()}Stream",
        (base_class,),
        class_props
    )
    # This is safe because DynamicStreamClass is created at runtime with all required abstract methods
    # implemented via the selected base class (IncrementalStream or FullTableStream) and class_props.
    return DynamicStreamClass(client, catalog_entry) # pylint: disable=abstract-class-instantiated


def deselect_unselected_fields(catalog_entry):
    """
    If a field isn't manually deselected, it will be included in the sync by default,
    so we must explicitly deselect any such fields in the catalog.
    """
    LOGGER.info("Deselecting unselected fields")
    mdata = metadata.to_map(catalog_entry.metadata)

    for breadcrumb, meta in mdata.items():
        if breadcrumb and meta.get('selected') is None:
            LOGGER.info("Deselecting field: %s", breadcrumb[-1])
            meta['selected'] = False

    catalog_entry.metadata = metadata.to_list(mdata)


def sync(client: Client, config: Dict, catalog: singer.Catalog, state) -> None:
    """
    Sync selected streams from catalog
    """

    streams_to_sync = []
    for stream in catalog.get_selected_streams(state):
        catalog_entry = catalog.get_stream(stream.tap_stream_id)
        if config.get('select_fields_by_default') is False:
            deselect_unselected_fields(catalog_entry)
        streams_to_sync.append(stream.tap_stream_id)

    LOGGER.info("selected_streams: {}".format(streams_to_sync))

    last_stream = singer.get_currently_syncing(state)
    LOGGER.info("last/currently syncing stream: {}".format(last_stream))

    with singer.Transformer() as transformer:
        for stream_name in streams_to_sync:
            if stream_name in STREAMS:
                stream = STREAMS[stream_name](client, catalog.get_stream(stream_name))
            else:
                stream = build_dynamic_stream(client, catalog.get_stream(stream_name))

            parent_name = getattr(stream, "parent", None)
            if parent_name:
                if parent_name not in streams_to_sync:
                    streams_to_sync.append(parent_name)
                continue

            write_schema(stream, client, streams_to_sync, catalog)
            LOGGER.info("START Syncing: {}".format(stream_name))
            update_currently_syncing(state, stream_name)
            total_records = stream.sync(state=state, transformer=transformer)

            update_currently_syncing(state, None)
            LOGGER.info(
                "FINISHED Syncing: {}, total_records: {}".format(
                    stream_name, total_records
                )
            )

