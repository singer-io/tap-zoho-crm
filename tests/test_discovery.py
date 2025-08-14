"""Test tap discovery mode and metadata."""
from base import Zoho_CRMBaseTest
from tap_tester.base_suite_tests.discovery_test import DiscoveryTest


class Zoho_CRMDiscoveryTest(DiscoveryTest, Zoho_CRMBaseTest):
    """Test tap discovery mode and metadata conforms to standards."""

    @staticmethod
    def name():
        return "tap_tester_zoho_crm_discovery_test"

    def streams_to_test(self):
        return self.expected_stream_names()

