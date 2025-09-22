
from base import Zoho_CRMBaseTest
from tap_tester.base_suite_tests.interrupted_sync_test import InterruptedSyncTest


class Zoho_CRMInterruptedSyncTest(Zoho_CRMBaseTest):
    """Test tap sets a bookmark and respects it for the next sync of a
    stream."""

    @staticmethod
    def name():
        return "tap_tester_zoho_crm_interrupted_sync_test"

    def streams_to_test(self):
        return self.expected_stream_names()


    def manipulate_state(self):
        return {
            "currently_syncing": "prospects",
            "bookmarks": {
                "appointments": { "Modified_Time" : "2020-01-01T00:00:00Z"},
                "currencies": { "modified_time" : "2020-01-01T00:00:00Z"},
                "profiles": { "modified_time" : "2020-01-01T00:00:00Z"},
                "roles": { "modified_time__s" : "2020-01-01T00:00:00Z"},
                "services": { "Modified_Time" : "2020-01-01T00:00:00Z"},
                "territories": { "modified_time" : "2020-01-01T00:00:00Z"},
                "users": { "Modified_Time" : "2020-01-01T00:00:00Z"},
        }
    }

