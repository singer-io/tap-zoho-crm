import sys
import json
import singer
from tap_zoho_crm.client import Client
from tap_zoho_crm.discover import discover
from tap_zoho_crm.sync import sync

LOGGER = singer.get_logger()

REQUIRED_CONFIG_KEYS = [
    'refresh_token',
    'client_id',
    'client_secret',
    'start_date',
    'api_version',
    'select_fields_by_default'
    ]

def do_discover(client: Client):
    """
    Discover and emit the catalog to stdout
    """
    LOGGER.info("Starting discover")
    catalog = discover(client=client)
    json.dump(catalog.to_dict(), sys.stdout, indent=2)
    LOGGER.info("Finished discover")


@singer.utils.handle_top_exception(LOGGER)
def main():
    """
    Run the tap
    """
    parsed_args = singer.utils.parse_args(REQUIRED_CONFIG_KEYS)
    state = {}
    if parsed_args.state:
        state = parsed_args.state

    with Client(parsed_args.config) as client:
        if parsed_args.discover:
            do_discover(client=client)
        elif parsed_args.catalog:
            sync(
                client=client,
                config=parsed_args.config,
                catalog=parsed_args.catalog,
                state=state)


if __name__ == "__main__":
    main()

