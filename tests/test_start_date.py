from base import ZohoCRMBaseTest
from tap_tester.base_suite_tests.start_date_test import StartDateTest



class ZohoCRMStartDateTest(StartDateTest, ZohoCRMBaseTest):
    """Instantiate start date according to the desired data set and run the
    test."""

    @staticmethod
    def name():
        return "tap_tester_zoho_crm_start_date_test"

    def streams_to_test(self):
        # Exclude streams that don't have enough test data to exceed the page_size
        streams_to_exclude = {
            'territories',
            'functions__s',
            'organization',
            'profiles',
            'roles',
            'events',
            'deals',
            'dealhistory',
            'notes',
            'attachments',
            'currencies'
        }
        return self.expected_stream_names().difference(streams_to_exclude)

    @property
    def start_date_1(self):
        return "2025-01-01T00:00:00Z"

    @property
    def start_date_2(self):
        return "2025-09-05T00:00:00Z"
