from tap_zoho_crm.streams.currencies import Currencies
from tap_zoho_crm.streams.organization import Organization
from tap_zoho_crm.streams.profiles import Profiles
from tap_zoho_crm.streams.roles import Roles
from tap_zoho_crm.streams.territories import Territories
from tap_zoho_crm.streams.users import Users

STREAMS = {
    "currencies": Currencies,
    "organization": Organization,
    "profiles": Profiles,
    "roles": Roles,
    "territories": Territories,
    "users": Users,
}

