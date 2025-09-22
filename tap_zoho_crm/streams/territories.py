from tap_zoho_crm.streams.abstracts import IncrementalStream

class Territories(IncrementalStream):
    tap_stream_id = "territories"
    key_properties = ["id"]
    replication_method = "INCREMENTAL"
    replication_keys = ["modified_time"]
    data_key = "territories"
    path = "settings/territories"

