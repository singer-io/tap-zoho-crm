from tap_zoho_crm.streams.abstracts import FullTableStream

class Profiles(FullTableStream):
    tap_stream_id = "profiles"
    key_properties = ["id"]
    replication_method = "FULL_TABLE"
    replication_keys = []
    data_key = "profiles"
    path = "settings/profiles"

