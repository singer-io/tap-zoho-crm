from tap_zoho_crm.streams.abstracts import IncrementalStream

class Services(IncrementalStream):
    tap_stream_id = "services"
    key_properties = ["id"]
    replication_method = "INCREMENTAL"
    replication_keys = ["Modified_Time"]
    data_key = "data"
    path = "/Services__s"

