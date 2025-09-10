from tap_zoho_crm.streams.abstracts import IncrementalStream

class Roles(IncrementalStream):
    tap_stream_id = "roles"
    key_properties = ["id"]
    replication_method = "INCREMENTAL"
    replication_keys = ["modified_time__s"]
    data_key = "roles"
    path = "settings/roles"
    pagination_supported = False

