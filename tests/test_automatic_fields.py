"""Test that with no fields selected for a stream automatic fields are still
replicated."""
from base import ZohoCRMBaseTest
from tap_tester.base_suite_tests.automatic_fields_test import MinimumSelectionTest


class ZohoCRMAutomaticFields(MinimumSelectionTest, ZohoCRMBaseTest):
    """Test that with no fields selected for a stream automatic fields are
    still replicated."""

    @staticmethod
    def name():
        return "tap_tester_zoho_crm_automatic_fields_test"

    def streams_to_test(self):
        # excluding dynamic schemas due to lack of test data
        streams_to_exclude = {
            'territories',
            'functions__s'
        }
        return self.expected_stream_names().difference(streams_to_exclude)
