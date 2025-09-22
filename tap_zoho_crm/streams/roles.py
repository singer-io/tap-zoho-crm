from tap_zoho_crm.streams.abstracts import FullTableStream

class Roles(FullTableStream):
    tap_stream_id = "roles"
    key_properties = ["id"]
    replication_method = "FULL_TABLE"
    replication_keys = []
    data_key = "roles"
    path = "settings/roles"
    pagination_supported = False

