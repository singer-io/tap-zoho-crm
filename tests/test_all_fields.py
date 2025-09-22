from base import Zoho_CRMBaseTest
from tap_tester.base_suite_tests.all_fields_test import AllFieldsTest

KNOWN_MISSING_FIELDS = {

}


class Zoho_CRMAllFields(AllFieldsTest, Zoho_CRMBaseTest):
    """Ensure running the tap with all streams and fields selected results in
    the replication of all fields."""

    @staticmethod
    def name():
        return "tap_tester_zoho_crm_all_fields_test"

    def streams_to_test(self):
        # excluding dynamic schemas due to lack of test data
        streams_to_exclude = {
            'Appointments_Rescheduled_History__s',
            'territories'
        }
        return self.expected_stream_names().difference(streams_to_exclude)

