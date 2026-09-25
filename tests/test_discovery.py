"""Test tap discovery mode and metadata."""
from base import ZohoCRMBaseTest
from tap_tester.base_suite_tests.discovery_test import DiscoveryTest


class ZohoCRMDiscoveryTest(DiscoveryTest, ZohoCRMBaseTest):
    """Test tap discovery mode and metadata conforms to standards."""

    @staticmethod
    def name():
        return "tap_tester_zoho_crm_discovery_test"

    def streams_to_test(self):
        # excluding dynamic schemas
        streams_to_exclude = {}
        return self.expected_stream_names().difference(streams_to_exclude)
