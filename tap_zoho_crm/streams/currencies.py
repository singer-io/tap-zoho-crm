from tap_zoho_crm.streams.abstracts import IncrementalStream

class Currencies(IncrementalStream):
    tap_stream_id = "currencies"
    key_properties = ["id"]
    replication_method = "INCREMENTAL"
    replication_keys = ["modified_time"]
    data_key = "currencies"
    path = "org/currencies"

