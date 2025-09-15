from tap_zoho_crm.streams.abstracts import FullTableStream

class Organization(FullTableStream):
    tap_stream_id = "organization"
    key_properties = ["id"]
    replication_method = "FULL_TABLE"
    replication_keys = []
    data_key = "org"
    path = "org"

