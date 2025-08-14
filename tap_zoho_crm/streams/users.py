from tap_zoho_crm.streams.abstracts import IncrementalStream

class Users(IncrementalStream):
    tap_stream_id = "users"
    key_properties = ["id"]
    replication_method = "INCREMENTAL"
    replication_keys = ["Modified_Time"]
    data_key = "users"
    path = "users"

