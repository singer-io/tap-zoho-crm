from tap_zoho_crm.streams.abstracts import IncrementalStream

class Appointments(IncrementalStream):
    tap_stream_id = "appointments"
    key_properties = ["id"]
    replication_method = "INCREMENTAL"
    replication_keys = ["Modified_Time"]
    data_key = "data"
    path = "Appointments__s"

