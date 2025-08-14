from tap_zoho_crm.streams.abstracts import IncrementalStream

class Profiles(IncrementalStream):
    tap_stream_id = "profiles"
    key_properties = ["id"]
    replication_method = "INCREMENTAL"
    replication_keys = ["modified_time"]
    data_key = "profiles"
    path = "settings/profiles"

