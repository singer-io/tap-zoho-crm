"""Test that with no fields selected for a stream automatic fields are still
replicated."""
from base import Zoho_CRMBaseTest
from tap_tester.base_suite_tests.automatic_fields_test import MinimumSelectionTest


class Zoho_CRMAutomaticFields(MinimumSelectionTest, Zoho_CRMBaseTest):
    """Test that with no fields selected for a stream automatic fields are
    still replicated."""

    @staticmethod
    def name():
        return "tap_tester_zoho_crm_automatic_fields_test"

    def streams_to_test(self):
        # excluding dynamic schemas due to lack of test data
        streams_to_exclude = {
            'Appointments_Rescheduled_History__s',
            'territories'
        }
        return self.expected_stream_names().difference(streams_to_exclude)

