"""Test tap discovery mode and metadata."""
from base import Zoho_CRMBaseTest
from tap_tester.base_suite_tests.discovery_test import DiscoveryTest


class Zoho_CRMDiscoveryTest(DiscoveryTest, Zoho_CRMBaseTest):
    """Test tap discovery mode and metadata conforms to standards."""

    @staticmethod
    def name():
        return "tap_tester_zoho_crm_discovery_test"

    def streams_to_test(self):
        # excluding dynamic schemas
        streams_to_exclude = {
            "Leads",
            "Accounts",
            "Calls",
            "Tasks",
            "Campaigns",
            "Deals",
            "Notes",
            "Calls",
            "DealHistory",
            "Attachments",
            "Contacts",
            "Appointments_Rescheduled_History__s",
            "Events"
        }
        return self.expected_stream_names().difference(streams_to_exclude)

