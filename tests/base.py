import copy
import os
import unittest
from datetime import datetime as dt
from datetime import timedelta

import dateutil.parser
import pytz
from tap_tester import connections, menagerie, runner
from tap_tester.logger import LOGGER
from tap_tester.base_suite_tests.base_case import BaseCase


class Zoho_CRMBaseTest(BaseCase):
    """Setup expectations for test sub classes.

    Metadata describing streams. A bunch of shared methods that are used
    in tap-tester tests. Shared tap-specific methods (as needed).
    """
    start_date = "2019-01-01T00:00:00Z"

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
                cls.API_LIMIT: 200
            },
            "organization": {
                cls.PRIMARY_KEYS: { "id" },
                cls.REPLICATION_METHOD: cls.FULL_TABLE,
                cls.REPLICATION_KEYS: set(),
                cls.OBEYS_START_DATE: False,
                cls.API_LIMIT: 200
            },
            "profiles": {
                cls.PRIMARY_KEYS: { "id" },
                cls.REPLICATION_METHOD: cls.INCREMENTAL,
                cls.REPLICATION_KEYS: { "modified_time" },
                cls.OBEYS_START_DATE: False,
                cls.API_LIMIT: 200
            },
            "roles": {
                cls.PRIMARY_KEYS: { "id" },
                cls.REPLICATION_METHOD: cls.INCREMENTAL,
                cls.REPLICATION_KEYS: { "modified_time__s" },
                cls.OBEYS_START_DATE: False,
                cls.API_LIMIT: 200
            },
            "territories": {
                cls.PRIMARY_KEYS: { "id" },
                cls.REPLICATION_METHOD: cls.INCREMENTAL,
                cls.REPLICATION_KEYS: { "modified_time" },
                cls.OBEYS_START_DATE: False,
                cls.API_LIMIT: 200
            },
            "users": {
                cls.PRIMARY_KEYS: { "id" },
                cls.REPLICATION_METHOD: cls.INCREMENTAL,
                cls.REPLICATION_KEYS: { "Modified_Time" },
                cls.OBEYS_START_DATE: False,
                cls.API_LIMIT: 200
            },
            # Dynamic Schemas for testing
            "leads": {
                cls.PRIMARY_KEYS: { "id" },
                cls.REPLICATION_METHOD: cls.INCREMENTAL,
                cls.REPLICATION_KEYS: { "Modified_Time" },
                cls.OBEYS_START_DATE: False,
                cls.API_LIMIT: 200
            },
            "accounts": {
                cls.PRIMARY_KEYS: { "id" },
                cls.REPLICATION_METHOD: cls.INCREMENTAL,
                cls.REPLICATION_KEYS: { "Modified_Time" },
                cls.OBEYS_START_DATE: False,
                cls.API_LIMIT: 200
            },
            "calls": {
                cls.PRIMARY_KEYS: { "id" },
                cls.REPLICATION_METHOD: cls.INCREMENTAL,
                cls.REPLICATION_KEYS: { "Modified_Time" },
                cls.OBEYS_START_DATE: False,
                cls.API_LIMIT: 200
            },
            "tasks": {
                cls.PRIMARY_KEYS: { "id" },
                cls.REPLICATION_METHOD: cls.INCREMENTAL,
                cls.REPLICATION_KEYS: { "Modified_Time" },
                cls.OBEYS_START_DATE: False,
                cls.API_LIMIT: 200
            },
            "campaigns": {
                cls.PRIMARY_KEYS: { "id" },
                cls.REPLICATION_METHOD: cls.INCREMENTAL,
                cls.REPLICATION_KEYS: { "Modified_Time" },
                cls.OBEYS_START_DATE: False,
                cls.API_LIMIT: 200
            },
            "deals": {
                cls.PRIMARY_KEYS: { "id" },
                cls.REPLICATION_METHOD: cls.INCREMENTAL,
                cls.REPLICATION_KEYS: { "Modified_Time" },
                cls.OBEYS_START_DATE: False,
                cls.API_LIMIT: 200
            },
            "notes": {
                cls.PRIMARY_KEYS: { "id" },
                cls.REPLICATION_METHOD: cls.INCREMENTAL,
                cls.REPLICATION_KEYS: { "Modified_Time" },
                cls.OBEYS_START_DATE: False,
                cls.API_LIMIT: 200
            },
            "dealhistory": {
                cls.PRIMARY_KEYS: { "id" },
                cls.REPLICATION_METHOD: cls.INCREMENTAL,
                cls.REPLICATION_KEYS: { "Modified_Time" },
                cls.OBEYS_START_DATE: False,
                cls.API_LIMIT: 200
            },
            "attachments": {
                cls.PRIMARY_KEYS: { "id" },
                cls.REPLICATION_METHOD: cls.INCREMENTAL,
                cls.REPLICATION_KEYS: { "Modified_Time" },
                cls.OBEYS_START_DATE: False,
                cls.API_LIMIT: 200
            },
            "contacts": {
                cls.PRIMARY_KEYS: { "id" },
                cls.REPLICATION_METHOD: cls.INCREMENTAL,
                cls.REPLICATION_KEYS: { "Modified_Time" },
                cls.OBEYS_START_DATE: False,
                cls.API_LIMIT: 200
            },
            "appointments_rescheduled_history__s": {
                cls.PRIMARY_KEYS: { "id" },
                cls.REPLICATION_METHOD: cls.INCREMENTAL,
                cls.REPLICATION_KEYS: { "Modified_Time" },
                cls.OBEYS_START_DATE: False,
                cls.API_LIMIT: 200
            },
            "functions__s": {
                cls.PRIMARY_KEYS: { "id" },
                cls.REPLICATION_METHOD: cls.INCREMENTAL,
                cls.REPLICATION_KEYS: { "modified_time" },
                cls.OBEYS_START_DATE: False,
                cls.API_LIMIT: 200
            },
            "events": {
                cls.PRIMARY_KEYS: { "id" },
                cls.REPLICATION_METHOD: cls.INCREMENTAL,
                cls.REPLICATION_KEYS: { "Modified_Time" },
                cls.OBEYS_START_DATE: False,
                cls.API_LIMIT: 200
            }
        }

    @staticmethod
    def get_credentials():
        """Authentication information for the test account."""
        credentials_dict = {}
        creds = {
            'client_id': 'TAP_ZOHO_CRM_CLIENT_ID',
            'client_secret': 'TAP_ZOHO_CRM_CLIENT_SECRET',
            'refresh_token': 'TAP_ZOHO_CRM_REFRESH_TOKEN',
            'select_fields_by_default': 'TAP_ZOHO_CRM_SELECT_FIELDS_BY_DEFAULT'
        }

        for cred in creds:
            credentials_dict[cred] = os.getenv(creds[cred])

        return credentials_dict

    def get_properties(self, original: bool = True):
        """Configuration of properties required for the tap."""
        return_value = {
            "start_date": "2022-07-01T00:00:00Z"
        }
        if original:
            return return_value

        return_value["start_date"] = self.start_date
        return return_value

