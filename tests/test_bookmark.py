from base import Zoho_CRMBaseTest
from tap_tester.base_suite_tests.bookmark_test import BookmarkTest


class Zoho_CRMBookMarkTest(BookmarkTest, Zoho_CRMBaseTest):
    """Test tap sets a bookmark and respects it for the next sync of a
    stream."""
    bookmark_format = "%Y-%m-%dT%H:%M:%S.%fZ"
    initial_bookmarks = {
        "bookmarks": {
            "currencies": { "modified_time" : "2020-01-01T00:00:00Z"},
            "profiles": { "modified_time" : "2020-01-01T00:00:00Z"},
            "roles": { "modified_time__s" : "2020-01-01T00:00:00Z"},
            "territories": { "modified_time" : "2020-01-01T00:00:00Z"},
            "users": { "Modified_Time" : "2020-01-01T00:00:00Z"},
        }
    }
    @staticmethod
    def name():
        return "tap_tester_zoho_crm_bookmark_test"

    def streams_to_test(self):
        streams_to_exclude = {}
        return self.expected_stream_names().difference(streams_to_exclude)

