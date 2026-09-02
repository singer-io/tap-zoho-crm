from base import ZohoCRMBaseTest
from tap_tester.base_suite_tests.bookmark_test import BookmarkTest


class ZohoCRMBookMarkTest(BookmarkTest, ZohoCRMBaseTest):
    """Test tap sets a bookmark and respects it for the next sync of a
    stream."""
    bookmark_format = "%Y-%m-%dT%H:%M:%S.%fZ"
    initial_bookmarks = {
        "bookmarks": {
            "leads":       {"Modified_Time": "2025-08-01T00:00:00Z"},
            "contacts":    {"Modified_Time": "2025-08-01T00:00:00Z"},
            "accounts":    {"Modified_Time": "2025-08-01T00:00:00Z"},
            "deals":       {"Modified_Time": "2025-08-01T00:00:00Z"},
            "calls":       {"Modified_Time": "2025-08-01T00:00:00Z"},
            "campaigns":   {"Modified_Time": "2025-08-01T00:00:00Z"},
            "dealhistory": {"Modified_Time": "2025-08-01T00:00:00Z"},
            "attachments": {"Modified_Time": "2025-08-01T00:00:00Z"},
        }
    }

    @staticmethod
    def name():
        return "tap_tester_zoho_crm_bookmark_test"

    def streams_to_test(self):
        streams_to_exclude = {
            'territories',
            'functions__s',
            # FULL_TABLE, no replication key
            'organization',
            'profiles',
            'roles',
            # lack of sufficient test data to verify bookmark behavior
            'currencies',
            'tasks',
            'notes',
            'events',
            'users'
        }
        return self.expected_stream_names().difference(streams_to_exclude)
