from tap_tester.base_suite_tests.pagination_test import PaginationTest
from base import ZohoCRMBaseTest

class ZohoCRMPaginationTest(PaginationTest, ZohoCRMBaseTest):
    """
    Ensure tap can replicate multiple pages of data for streams that use pagination.
    """

    @staticmethod
    def name():
        return "tap_tester_zoho_crm_pagination_test"

    def streams_to_test(self):
        # Exclude streams that don't have enough test data to exceed the page_size
        streams_to_exclude = {
            'territories',
            'functions__s',
            'currencies',
            'organization',
            'profiles',
            'roles',
            'users',
            'calls',
            'campaigns',
            'attachments'
        }
        return self.expected_stream_names().difference(streams_to_exclude)
