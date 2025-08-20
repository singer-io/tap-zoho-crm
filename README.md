# tap-zoho-crm

This is a [Singer](https://singer.io) tap that produces JSON-formatted data
following the [Singer
spec](https://github.com/singer-io/getting-started/blob/master/docs/SPEC.md).

This tap:

- Pulls raw data from the [Zoho_CRM API].
- Extracts the following resources:
    - [Appointments](https://www.zoho.com/crm/developer/docs/api/v8/get-appointments.html)

    - [Currencies](https://www.zoho.com/crm/developer/docs/api/v8/get-currencies-data.html)

    - [Organization](https://www.zoho.com/crm/developer/docs/api/v8/get-org-data.html)

    - [Profiles](https://www.zoho.com/crm/developer/docs/api/v8/get-profiles.html)

    - [Roles](https://www.zoho.com/crm/developer/docs/api/v8/get-roles.html)

    - [Services](https://www.zoho.com/crm/developer/docs/api/v8/get-services.html)

    - [Territories](https://www.zoho.com/crm/developer/docs/api/v8/territories.html)

    - [Users](https://www.zoho.com/crm/developer/docs/api/v8/get-users.html)

- Outputs the schema for each resource
- Incrementally pulls data based on the input state


## Streams


**[appointments](https://www.zoho.com/crm/developer/docs/api/v8/get-appointments.html)**
- Data Key = data
- Primary keys: ['id']
- Replication strategy: INCREMENTAL

**[currencies](https://www.zoho.com/crm/developer/docs/api/v8/get-currencies-data.html)**
- Data Key = data
- Primary keys: ['id']
- Replication strategy: INCREMENTAL

**[organization](https://www.zoho.com/crm/developer/docs/api/v8/get-org-data.html)**
- Data Key = org
- Primary keys: ['id']
- Replication strategy: FULL_TABLE

**[profiles](https://www.zoho.com/crm/developer/docs/api/v8/get-profiles.html)**
- Data Key = profiles
- Primary keys: ['id']
- Replication strategy: INCREMENTAL

**[roles](https://www.zoho.com/crm/developer/docs/api/v8/get-roles.html)**
- Data Key = roles
- Primary keys: ['id']
- Replication strategy: INCREMENTAL

**[services](https://www.zoho.com/crm/developer/docs/api/v8/get-services.html)**
- Data Key = data
- Primary keys: ['id']
- Replication strategy: INCREMENTAL

**[territories](https://www.zoho.com/crm/developer/docs/api/v8/territories.html)**
- Data Key = territories
- Primary keys: ['id']
- Replication strategy: INCREMENTAL

**[users](https://www.zoho.com/crm/developer/docs/api/v8/get-users.html)**
- Data Key = users
- Primary keys: ['id']
- Replication strategy: INCREMENTAL



## Authentication

## Quick Start

1. Install

    Clone this repository, and then install using setup.py. We recommend using a virtualenv:

    ```bash
    > virtualenv -p python3 venv
    > source venv/bin/activate
    > python setup.py install
    OR
    > cd .../tap-zoho_crm
    > pip install -e .
    ```
2. Dependent libraries. The following dependent libraries were installed.
    ```bash
    > pip install singer-python
    > pip install target-stitch
    > pip install target-json

    ```
    - [singer-tools](https://github.com/singer-io/singer-tools)
    - [target-stitch](https://github.com/singer-io/target-stitch)

3. Create your tap's `config.json` file.  The tap config file for this tap should include these entries:
   - `client_id` - User account client id should be provided
   - `client_secret` - User account client secret should be provided
   - `refresh_token` - User account refresh token should be provided
   - `start_date` - the default value to use if no bookmark exists for an endpoint (rfc3339 date string)
   - `user_agent` - (string, optional): Process and email for API logging purposes. Example: `tap-zoho-crm <api_user_email@your_company.com>`
   - `api_version` - (string) Current api version which we are using to extract data.
   - `auto_add_new_data` - (boolean-true/false) If we want to add new metadata fields, which are added to module/stream after running discovery.
   - `request_timeout` - (integer, `300`): Max time for which request should wait to get a response. Default request_timeout is 300 seconds.

    ```json
    {
        "client_id": "the_client_id",
        "client_secret": "the_client_secret",
        "refresh_token": "the_refresh_token",
        "start_date": "2019-01-01T00:00:00Z",
        "user_agent": "tap-zoho-crm <api_user_email@your_company.com>",
        "api_version": "v8",
        "auto_add_new_data": false,
        "request_timeout": 300
    }
    ```

    Optionally, also create a `state.json` file. `currently_syncing` is an optional attribute used for identifying the last object to be synced in case the job is interrupted mid-stream. The next run would begin where the last job left off.

    ```json
    {
        "currently_syncing": "engage",
        "bookmarks": {
            "export": "2019-09-27T22:34:39.000000Z",
            "funnels": "2019-09-28T15:30:26.000000Z",
            "revenue": "2019-09-28T18:23:53Z"
        }
    }
    ```

4. Run the Tap in Discovery Mode
    This creates a catalog.json for selecting objects/fields to integrate:
    ```bash
    tap-zoho-crm --config config.json --discover > catalog.json
    ```
   See the Singer docs on discovery mode
   [here](https://github.com/singer-io/getting-started/blob/master/docs/DISCOVERY_MODE.md#discovery-mode).

5. Run the Tap in Sync Mode (with catalog) and [write out to state file](https://github.com/singer-io/getting-started/blob/master/docs/RUNNING_AND_DEVELOPING.md#running-a-singer-tap-with-a-singer-target)

    For Sync mode:
    ```bash
    > tap-zoho-crm --config tap_config.json --catalog catalog.json > state.json
    > tail -1 state.json > state.json.tmp && mv state.json.tmp state.json
    ```
    To load to json files to verify outputs:
    ```bash
    > tap-zoho-crm --config tap_config.json --catalog catalog.json | target-json > state.json
    > tail -1 state.json > state.json.tmp && mv state.json.tmp state.json
    ```
    To pseudo-load to [Stitch Import API](https://github.com/singer-io/target-stitch) with dry run:
    ```bash
    > tap-zoho-crm --config tap_config.json --catalog catalog.json | target-stitch --config target_config.json --dry-run > state.json
    > tail -1 state.json > state.json.tmp && mv state.json.tmp state.json
    ```

6. Test the Tap
    While developing the zoho_crm tap, the following utilities were run in accordance with Singer.io best practices:
    Pylint to improve [code quality](https://github.com/singer-io/getting-started/blob/master/docs/BEST_PRACTICES.md#code-quality):
    ```bash
    > pylint tap_zoho_crm -d missing-docstring -d logging-format-interpolation -d too-many-locals -d too-many-arguments
    ```
    Pylint test resulted in the following score:
    ```bash
    Your code has been rated at 9.67/10
    ```

    To [check the tap](https://github.com/singer-io/singer-tools#singer-check-tap) and verify working:
    ```bash
    > tap-zoho-crm --config tap_config.json --catalog catalog.json | singer-check-tap > state.json
    > tail -1 state.json > state.json.tmp && mv state.json.tmp state.json
    ```

    #### Unit Tests

    Unit tests may be run with the following.

    ```
    python -m pytest --verbose
    ```

    Note, you may need to install test dependencies.

    ```
    pip install -e .'[dev]'
    ```
---

Copyright &copy; 2019 Stitch
