import os

from tap_tester.logger import LOGGER
from tap_tester.base_suite_tests.base_case import BaseCase



class ZohoCRMBaseTest(BaseCase):
    """Setup expectations for test sub classes.

    Metadata describing streams. A bunch of shared methods that are used
    in tap-tester tests. Shared tap-specific methods (as needed).
    """
    start_date = "2025-01-01T00:00:00Z"
    IS_FORBIDDEN_STREAM = "is-forbidden-stream"

    @staticmethod
    def tap_name():
        """The name of the tap."""
        return "tap-zoho-crm"

    @staticmethod
    def get_type():
        """The name of the tap."""
        return "platform.zoho_crm"

    @classmethod
    def expected_metadata(cls):
        """The expected streams and metadata about the streams."""
        return {
            "currencies": {
                cls.PRIMARY_KEYS: { "id" },
                cls.REPLICATION_METHOD: cls.INCREMENTAL,
                cls.REPLICATION_KEYS: { "modified_time" },
                cls.OBEYS_START_DATE: False,
                cls.API_LIMIT: 5
            },
            "organization": {
                cls.PRIMARY_KEYS: { "id" },
                cls.REPLICATION_METHOD: cls.FULL_TABLE,
                cls.REPLICATION_KEYS: set(),
                cls.OBEYS_START_DATE: False,
                cls.API_LIMIT: 5
            },
            "profiles": {
                cls.PRIMARY_KEYS: { "id" },
                cls.REPLICATION_METHOD: cls.FULL_TABLE,
                cls.REPLICATION_KEYS: set(),
                cls.OBEYS_START_DATE: False,
                cls.API_LIMIT: 5
            },
            "roles": {
                cls.PRIMARY_KEYS: { "id" },
                cls.REPLICATION_METHOD: cls.FULL_TABLE,
                cls.REPLICATION_KEYS: set(),
                cls.OBEYS_START_DATE: False,
                cls.API_LIMIT: 5
            },
            "territories": {
                cls.PRIMARY_KEYS: { "id" },
                cls.REPLICATION_METHOD: cls.INCREMENTAL,
                cls.REPLICATION_KEYS: { "modified_time" },
                cls.OBEYS_START_DATE: False,
                cls.API_LIMIT: 5,
                cls.IS_FORBIDDEN_STREAM: True
            },
            "users": {
                cls.PRIMARY_KEYS: { "id" },
                cls.REPLICATION_METHOD: cls.INCREMENTAL,
                cls.REPLICATION_KEYS: { "Modified_Time" },
                cls.OBEYS_START_DATE: False,
                cls.API_LIMIT: 5
            },
            # Dynamic Schemas for testing
            "leads": {
                cls.PRIMARY_KEYS: { "id" },
                cls.REPLICATION_METHOD: cls.INCREMENTAL,
                cls.REPLICATION_KEYS: { "Modified_Time" },
                cls.OBEYS_START_DATE: False,
                cls.API_LIMIT: 5
            },
            "accounts": {
                cls.PRIMARY_KEYS: { "id" },
                cls.REPLICATION_METHOD: cls.INCREMENTAL,
                cls.REPLICATION_KEYS: { "Modified_Time" },
                cls.OBEYS_START_DATE: False,
                cls.API_LIMIT: 5
            },
            "calls": {
                cls.PRIMARY_KEYS: { "id" },
                cls.REPLICATION_METHOD: cls.INCREMENTAL,
                cls.REPLICATION_KEYS: { "Modified_Time" },
                cls.OBEYS_START_DATE: False,
                cls.API_LIMIT: 5
            },
            "tasks": {
                cls.PRIMARY_KEYS: { "id" },
                cls.REPLICATION_METHOD: cls.INCREMENTAL,
                cls.REPLICATION_KEYS: { "Modified_Time" },
                cls.OBEYS_START_DATE: False,
                cls.API_LIMIT: 5
            },
            "campaigns": {
                cls.PRIMARY_KEYS: { "id" },
                cls.REPLICATION_METHOD: cls.INCREMENTAL,
                cls.REPLICATION_KEYS: { "Modified_Time" },
                cls.OBEYS_START_DATE: False,
                cls.API_LIMIT: 5
            },
            "deals": {
                cls.PRIMARY_KEYS: { "id" },
                cls.REPLICATION_METHOD: cls.INCREMENTAL,
                cls.REPLICATION_KEYS: { "Modified_Time" },
                cls.OBEYS_START_DATE: False,
                cls.API_LIMIT: 5
            },
            "notes": {
                cls.PRIMARY_KEYS: { "id" },
                cls.REPLICATION_METHOD: cls.INCREMENTAL,
                cls.REPLICATION_KEYS: { "Modified_Time" },
                cls.OBEYS_START_DATE: False,
                cls.API_LIMIT: 5
            },
            "dealhistory": {
                cls.PRIMARY_KEYS: { "id" },
                cls.REPLICATION_METHOD: cls.INCREMENTAL,
                cls.REPLICATION_KEYS: { "Modified_Time" },
                cls.OBEYS_START_DATE: False,
                cls.API_LIMIT: 5
            },
            "attachments": {
                cls.PRIMARY_KEYS: { "id" },
                cls.REPLICATION_METHOD: cls.INCREMENTAL,
                cls.REPLICATION_KEYS: { "Modified_Time" },
                cls.OBEYS_START_DATE: False,
                cls.API_LIMIT: 5
            },
            "contacts": {
                cls.PRIMARY_KEYS: { "id" },
                cls.REPLICATION_METHOD: cls.INCREMENTAL,
                cls.REPLICATION_KEYS: { "Modified_Time" },
                cls.OBEYS_START_DATE: False,
                cls.API_LIMIT: 5
            },
            "appointments_rescheduled_history__s": {
                cls.PRIMARY_KEYS: { "id" },
                cls.REPLICATION_METHOD: cls.INCREMENTAL,
                cls.REPLICATION_KEYS: { "Modified_Time" },
                cls.OBEYS_START_DATE: False,
                cls.API_LIMIT: 5,
                cls.IS_FORBIDDEN_STREAM: True
            },
            "functions__s": {
                cls.PRIMARY_KEYS: { "id" },
                cls.REPLICATION_METHOD: cls.INCREMENTAL,
                cls.REPLICATION_KEYS: { "modified_time" },
                cls.OBEYS_START_DATE: False,
                cls.API_LIMIT: 5
            },
            "events": {
                cls.PRIMARY_KEYS: { "id" },
                cls.REPLICATION_METHOD: cls.INCREMENTAL,
                cls.REPLICATION_KEYS: { "Modified_Time" },
                cls.OBEYS_START_DATE: False,
                cls.API_LIMIT: 5
            }
        }

    @staticmethod
    def get_credentials():
        """Authentication information for the test account."""
        credentials_dict = {}
        creds = {
            'client_id': 'TAP_ZOHO_CRM_CLIENT_ID',
            'client_secret': 'TAP_ZOHO_CRM_CLIENT_SECRET',
            'refresh_token': 'TAP_ZOHO_CRM_REFRESH_TOKEN'
        }

        for cred in creds:
            credentials_dict[cred] = os.getenv(creds[cred])

        return credentials_dict

    def expected_stream_names(self):
        """The expected stream names and exclude forbidden streams."""
        return {
            stream_name
            for stream_name, metadata in self.expected_metadata().items()
            if not metadata.get(self.IS_FORBIDDEN_STREAM, False)
        }

    def get_properties(self, original: bool = True):
        """Configuration of properties required for the tap."""
        return_value = {
            "start_date": self.start_date,
            "page_size": "5"
        }
        if original:
            return return_value

        return_value["start_date"] = self.start_date
        return return_value

