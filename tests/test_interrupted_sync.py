
from base import ZohoCRMBaseTest
from tap_tester.base_suite_tests.interrupted_sync_test import InterruptedSyncTest


class ZohoCRMInterruptedSyncTest(InterruptedSyncTest, ZohoCRMBaseTest):
    """Test tap sets a bookmark and respects it for the next sync of a
    stream."""

    @staticmethod
    def name():
        return "tap_tester_zoho_crm_interrupted_sync_test"

    def streams_to_test(self):
        # excluding streams because no data and full table replication method
        streams_to_exclude = {
            'territories',
            'functions__s',
            'organization',
            'profiles',
            'roles',
            'currencies'
        }
        return self.expected_stream_names().difference(streams_to_exclude)


    def manipulate_state(self):
        return {
            "currently_syncing": "deals",
            "bookmarks": {
                "users": {"Modified_Time": "2025-09-16T02:42:47.000000Z"},
                "leads": {"Modified_Time": "2026-06-03T09:12:54.000000Z"},
                "contacts": {"Modified_Time": "2025-09-16T02:23:30.000000Z"},
                "accounts": {"Modified_Time": "2025-09-16T02:25:23.000000Z"},
                "deals": {"Modified_Time": "2025-09-01T00:00:00.000000Z"},
            }
        }
