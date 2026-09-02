import unittest
from unittest.mock import patch, MagicMock
from tap_zoho_crm.streams.abstracts import (
    IncrementalStream,
    FullTableStream,
    ParentBaseStream,
    ChildBaseStream,
)


# ---------------------------------------------------------------------------
# Concrete test implementations
# ---------------------------------------------------------------------------

class ConcreteIncrementalStream(IncrementalStream):
    @property
    def tap_stream_id(self): return "test_inc_stream"
    @property
    def replication_method(self): return "INCREMENTAL"
    @property
    def key_properties(self): return ["id"]
    @property
    def replication_keys(self): return ["updated_at"]
    path = "test_path"
    data_key = "data"


class ConcreteFullTableStream(FullTableStream):
    @property
    def tap_stream_id(self): return "test_ft_stream"
    @property
    def replication_method(self): return "FULL_TABLE"
    @property
    def key_properties(self): return ["id"]
    path = "test_path"
    data_key = "data"


class ConcreteChildStream(ChildBaseStream):
    @property
    def tap_stream_id(self): return "child_stream"
    @property
    def replication_method(self): return "INCREMENTAL"
    @property
    def key_properties(self): return ["id"]
    @property
    def replication_keys(self): return ["updated_at"]
    path = "parent/{}/children"
    data_key = "data"


# ---------------------------------------------------------------------------
# Helper to build a stream instance with mocked catalog
# ---------------------------------------------------------------------------

def _make_stream(cls, schema_props=None, client=None):
    with patch('tap_zoho_crm.streams.abstracts.metadata.to_map', return_value={}):
        mock_catalog = MagicMock()
        mock_catalog.schema.to_dict.return_value = {
            "properties": schema_props or {"id": {}, "updated_at": {}}
        }
        mock_catalog.metadata = []
        stream = cls(catalog=mock_catalog)

    if client is not None:
        stream.client = client
    else:
        stream.client = MagicMock()
        stream.client.config = {"start_date": "2020-01-01T00:00:00Z"}
        stream.client.base_url = "https://www.zohoapis.com/crm/v8"

    stream.child_to_sync = []
    return stream


# ---------------------------------------------------------------------------
# BaseStream helper methods
# ---------------------------------------------------------------------------

class TestBaseStreamHelpers(unittest.TestCase):

    def setUp(self):
        self.stream = _make_stream(ConcreteIncrementalStream)
        self.stream.url_endpoint = ""

    def test_update_params_updates_stream_params(self):
        self.stream.update_params(page=2, per_page=100)
        self.assertEqual(self.stream.params["page"], 2)
        self.assertEqual(self.stream.params["per_page"], 100)

    def test_update_data_payload_updates_payload(self):
        self.stream.update_data_payload(parent_obj={"id": "abc"})
        self.assertEqual(self.stream.data_payload["parent_obj"], {"id": "abc"})

    def test_modify_object_returns_record_unchanged(self):
        record = {"id": "1", "updated_at": "2021-01-01"}
        result = self.stream.modify_object(record)
        self.assertEqual(result, record)

    def test_get_url_endpoint_uses_url_endpoint_when_set(self):
        self.stream.url_endpoint = "https://explicit.example.com/api"
        result = self.stream.get_url_endpoint()
        self.assertEqual(result, "https://explicit.example.com/api")

    def test_get_url_endpoint_builds_from_base_url_and_path(self):
        self.stream.url_endpoint = ""
        result = self.stream.get_url_endpoint()
        self.assertEqual(result, "https://www.zohoapis.com/crm/v8/test_path")

    def test_write_schema_success(self):
        with patch('tap_zoho_crm.streams.abstracts.write_schema') as mock_ws:
            self.stream.write_schema()
            mock_ws.assert_called_once_with("test_inc_stream", self.stream.schema, ["id"])

    def test_write_schema_raises_on_os_error(self):
        with patch('tap_zoho_crm.streams.abstracts.write_schema', side_effect=OSError("disk full")):
            with self.assertRaises(OSError):
                self.stream.write_schema()


# ---------------------------------------------------------------------------
# update_pagination_key
# ---------------------------------------------------------------------------

class TestUpdatePaginationKey(unittest.TestCase):

    def setUp(self):
        self.stream = _make_stream(ConcreteIncrementalStream)

    def test_returns_none_when_pagination_not_supported(self):
        self.stream.pagination_supported = False
        result = self.stream.update_pagination_key({"info": {"more_records": True}}, 1)
        self.assertIsNone(result)

    def test_returns_none_when_raw_records_is_none(self):
        result = self.stream.update_pagination_key(None, 1)
        self.assertIsNone(result)

    def test_returns_none_when_no_info_key(self):
        result = self.stream.update_pagination_key({"data": []}, 1)
        self.assertIsNone(result)

    def test_uses_next_page_token_when_present(self):
        raw = {"info": {"next_page_token": "tok123"}}
        result = self.stream.update_pagination_key(raw, 1)
        self.assertEqual(result, "tok123")
        self.assertEqual(self.stream.params.get("page_token"), "tok123")

    def test_increments_page_when_more_records(self):
        raw = {"info": {"more_records": True}}
        result = self.stream.update_pagination_key(raw, 1)
        self.assertEqual(result, 2)
        self.assertEqual(self.stream.params.get("page"), 2)

    def test_returns_none_when_no_more_records_and_no_token(self):
        raw = {"info": {"more_records": False}}
        result = self.stream.update_pagination_key(raw, 1)
        self.assertIsNone(result)


# ---------------------------------------------------------------------------
# get_records – static stream
# ---------------------------------------------------------------------------

class TestGetRecordsStaticStream(unittest.TestCase):

    def setUp(self):
        self.stream = _make_stream(ConcreteIncrementalStream)
        self.stream.url_endpoint = "https://www.zohoapis.com/crm/v8/test_path"

    def test_get_records_single_page(self):
        """Single page: yields records and stops when no more_records."""
        page_resp = {"data": [{"id": "1"}, {"id": "2"}], "info": {"more_records": False}}
        self.stream.client.make_request.return_value = page_resp

        records = list(self.stream.get_records())
        self.assertEqual(len(records), 2)
        self.assertEqual(records[0]["id"], "1")

    def test_get_records_multiple_pages(self):
        """Multi-page: yields records from all pages."""
        page1 = {"data": [{"id": "1"}], "info": {"more_records": True}}
        page2 = {"data": [{"id": "2"}], "info": {"more_records": False}}
        self.stream.client.make_request.side_effect = [page1, page2]

        records = list(self.stream.get_records())
        self.assertEqual(len(records), 2)

    def test_get_records_empty_response(self):
        """Returns empty when API returns no data key."""
        self.stream.client.make_request.return_value = {"info": {"more_records": False}}
        records = list(self.stream.get_records())
        self.assertEqual(records, [])

    def test_get_records_with_next_page_token(self):
        """Pagination via next_page_token."""
        page1 = {"data": [{"id": "1"}], "info": {"next_page_token": "tok_abc"}}
        page2 = {"data": [{"id": "2"}], "info": {}}
        self.stream.client.make_request.side_effect = [page1, page2]

        records = list(self.stream.get_records())
        self.assertEqual(len(records), 2)


# ---------------------------------------------------------------------------
# get_records – dynamic stream
# ---------------------------------------------------------------------------

class TestGetRecordsDynamicStream(unittest.TestCase):

    def setUp(self):
        # Build a dynamic stream with 3 fields (< FIELD_BATCH_SIZE=50)
        props = {f"field_{i}": {} for i in range(3)}
        props["id"] = {}
        self.stream = _make_stream(ConcreteIncrementalStream, schema_props=props)
        self.stream.is_dynamic = True
        self.stream.url_endpoint = "https://www.zohoapis.com/crm/v8/test_path"

    def test_get_records_dynamic_merges_by_id(self):
        """Dynamic records are merged by id across field batches."""
        batch_resp = {
            "data": [{"id": "1", "field_0": "a"}, {"id": "2", "field_0": "b"}],
            "info": {"more_records": False}
        }
        self.stream.client.make_request.return_value = batch_resp

        records = list(self.stream.get_records())
        self.assertEqual(len(records), 2)

    def test_get_records_dynamic_skips_records_without_id(self):
        """Records without an 'id' field are skipped."""
        batch_resp = {
            "data": [{"field_0": "no_id_here"}],
            "info": {"more_records": False}
        }
        self.stream.client.make_request.return_value = batch_resp

        records = list(self.stream.get_records())
        self.assertEqual(records, [])

    def test_get_records_dynamic_no_response(self):
        """If make_request returns empty, no records are yielded."""
        batch_resp = {"data": [], "info": {"more_records": False}}
        self.stream.client.make_request.return_value = batch_resp

        records = list(self.stream.get_records())
        self.assertEqual(records, [])


# ---------------------------------------------------------------------------
# IncrementalStream.get_bookmark / write_bookmark
# ---------------------------------------------------------------------------

class TestIncrementalStreamBookmarks(unittest.TestCase):

    def setUp(self):
        self.stream = _make_stream(ConcreteIncrementalStream)

    @patch('tap_zoho_crm.streams.abstracts.get_bookmark', return_value="2021-01-01")
    def test_get_bookmark_delegates_to_singer(self, mock_gb):
        state = {}
        result = self.stream.get_bookmark(state, "test_inc_stream")
        mock_gb.assert_called_once_with(
            state, "test_inc_stream", "updated_at", "2020-01-01T00:00:00Z"
        )
        self.assertEqual(result, "2021-01-01")

    def test_write_bookmark_returns_state_when_no_key_and_no_replication_keys(self):
        """Returns original state when neither key nor replication_keys is set."""
        # Create an IncrementalStream subclass with empty replication_keys
        class NoRepKeyStream(IncrementalStream):
            @property
            def tap_stream_id(self): return "no_rep_stream"
            @property
            def replication_method(self): return "INCREMENTAL"
            @property
            def key_properties(self): return ["id"]
            @property
            def replication_keys(self): return []

        stream = _make_stream(NoRepKeyStream)
        state = {"bookmarks": {}}
        result = stream.write_bookmark(state, "no_rep_stream", key=None, value="2021-01-01")
        # Should return state unchanged because key=None and replication_keys=[]
        self.assertEqual(result, state)


# ---------------------------------------------------------------------------
# IncrementalStream.sync
# ---------------------------------------------------------------------------

class TestIncrementalStreamSync(unittest.TestCase):

    def setUp(self):
        self.stream = _make_stream(ConcreteIncrementalStream)
        self.stream.schema = {"properties": {"id": {}, "updated_at": {}}}

    @patch('tap_zoho_crm.streams.abstracts.write_record')
    @patch('tap_zoho_crm.streams.abstracts.write_bookmark')
    @patch('tap_zoho_crm.streams.abstracts.get_bookmark', return_value="2021-01-01")
    def test_sync_writes_records_at_or_after_bookmark(
        self, mock_gb, mock_wb, mock_wr
    ):
        """Records with timestamp >= bookmark are written."""
        self.stream.get_records = MagicMock(return_value=[
            {"id": "1", "updated_at": "2021-06-01"},
            {"id": "2", "updated_at": "2020-06-01"},  # before bookmark → skipped
        ])
        self.stream.is_selected = MagicMock(return_value=True)

        mock_transformer = MagicMock()
        mock_transformer.transform.side_effect = lambda r, s, m: r

        state = {}
        self.stream.sync(state=state, transformer=mock_transformer)

        # Only the first record passes the bookmark check
        mock_wr.assert_called_once_with("test_inc_stream", {"id": "1", "updated_at": "2021-06-01"})

    @patch('tap_zoho_crm.streams.abstracts.write_record')
    @patch('tap_zoho_crm.streams.abstracts.write_bookmark')
    @patch('tap_zoho_crm.streams.abstracts.get_bookmark', return_value="2021-01-01")
    def test_sync_skips_write_when_not_selected(
        self, mock_gb, mock_wb, mock_wr
    ):
        """Records are not written to output when stream is not selected."""
        self.stream.get_records = MagicMock(return_value=[
            {"id": "1", "updated_at": "2021-06-01"},
        ])
        self.stream.is_selected = MagicMock(return_value=False)

        mock_transformer = MagicMock()
        mock_transformer.transform.side_effect = lambda r, s, m: r

        state = {}
        self.stream.sync(state=state, transformer=mock_transformer)

        mock_wr.assert_not_called()

    @patch('tap_zoho_crm.streams.abstracts.write_record')
    @patch('tap_zoho_crm.streams.abstracts.write_bookmark')
    @patch('tap_zoho_crm.streams.abstracts.get_bookmark', return_value="2021-01-01")
    def test_sync_calls_child_sync_for_qualifying_records(
        self, mock_gb, mock_wb, mock_wr
    ):
        """Child streams are synced for each qualifying parent record."""
        record = {"id": "1", "updated_at": "2021-06-01"}
        self.stream.get_records = MagicMock(return_value=[record])
        self.stream.is_selected = MagicMock(return_value=True)

        mock_child = MagicMock()
        self.stream.child_to_sync = [mock_child]

        mock_transformer = MagicMock()
        mock_transformer.transform.side_effect = lambda r, s, m: r

        state = {}
        self.stream.sync(state=state, transformer=mock_transformer)

        mock_child.sync.assert_called_once()

    @patch('tap_zoho_crm.streams.abstracts.write_record')
    @patch('tap_zoho_crm.streams.abstracts.write_bookmark')
    @patch('tap_zoho_crm.streams.abstracts.get_bookmark', return_value="2021-01-01")
    def test_sync_logs_critical_when_replication_key_is_none(
        self, mock_gb, mock_wb, mock_wr
    ):
        """LOGGER.critical is called when the replication key value is None."""
        self.stream.get_records = MagicMock(return_value=[
            {"id": "1", "updated_at": None},
        ])
        self.stream.is_selected = MagicMock(return_value=True)

        mock_transformer = MagicMock()
        mock_transformer.transform.side_effect = lambda r, s, m: r

        with patch('tap_zoho_crm.streams.abstracts.LOGGER') as mock_logger:
            state = {}
            try:
                self.stream.sync(state=state, transformer=mock_transformer)
            except TypeError:
                # None >= "2021-01-01" raises TypeError; that's expected here
                pass
        mock_logger.critical.assert_called_once()


# ---------------------------------------------------------------------------
# FullTableStream.sync
# ---------------------------------------------------------------------------

class TestFullTableStreamSync(unittest.TestCase):

    def setUp(self):
        self.stream = _make_stream(ConcreteFullTableStream)
        self.stream.schema = {"properties": {"id": {}}}

    @patch('tap_zoho_crm.streams.abstracts.write_record')
    def test_sync_writes_all_records_when_selected(self, mock_wr):
        """All records are written when stream is selected."""
        self.stream.get_records = MagicMock(return_value=[{"id": "1"}, {"id": "2"}])
        self.stream.is_selected = MagicMock(return_value=True)

        mock_transformer = MagicMock()
        mock_transformer.transform.side_effect = lambda r, s, m: r

        count = self.stream.sync(state={}, transformer=mock_transformer)

        self.assertEqual(mock_wr.call_count, 2)
        self.assertEqual(count, 2)

    @patch('tap_zoho_crm.streams.abstracts.write_record')
    def test_sync_skips_write_when_not_selected(self, mock_wr):
        """Records are not written when stream is not selected."""
        self.stream.get_records = MagicMock(return_value=[{"id": "1"}])
        self.stream.is_selected = MagicMock(return_value=False)

        mock_transformer = MagicMock()
        mock_transformer.transform.side_effect = lambda r, s, m: r

        count = self.stream.sync(state={}, transformer=mock_transformer)

        mock_wr.assert_not_called()
        self.assertEqual(count, 0)

    @patch('tap_zoho_crm.streams.abstracts.write_record')
    def test_sync_calls_child_sync_for_every_record(self, mock_wr):
        """Children are synced for every record regardless of selection."""
        self.stream.get_records = MagicMock(return_value=[{"id": "1"}, {"id": "2"}])
        self.stream.is_selected = MagicMock(return_value=True)

        mock_child = MagicMock()
        self.stream.child_to_sync = [mock_child]

        mock_transformer = MagicMock()
        mock_transformer.transform.side_effect = lambda r, s, m: r

        self.stream.sync(state={}, transformer=mock_transformer)

        self.assertEqual(mock_child.sync.call_count, 2)


# ---------------------------------------------------------------------------
# ParentBaseStream.write_bookmark
# ---------------------------------------------------------------------------

class ConcreteParentStream(ParentBaseStream):
    @property
    def tap_stream_id(self): return "parent_stream"
    @property
    def replication_method(self): return "INCREMENTAL"
    @property
    def key_properties(self): return ["id"]
    @property
    def replication_keys(self): return ["updated_at"]
    path = "parent_path"
    data_key = "data"


class TestParentBaseStreamWriteBookmark(unittest.TestCase):

    def setUp(self):
        self.stream = _make_stream(ConcreteParentStream)

    @patch('tap_zoho_crm.streams.abstracts.IncrementalStream.write_bookmark')
    def test_write_bookmark_writes_parent_when_selected(self, mock_super_wb):
        """write_bookmark writes parent bookmark when is_selected is True."""
        mock_super_wb.return_value = {"bookmarks": {}}
        self.stream.is_selected = MagicMock(return_value=True)

        state = {}
        self.stream.write_bookmark(state, "parent_stream", value="2021-01-01")

        mock_super_wb.assert_called()

    @patch('tap_zoho_crm.streams.abstracts.IncrementalStream.write_bookmark')
    def test_write_bookmark_writes_child_bookmarks(self, mock_super_wb):
        """write_bookmark always writes child bookmarks."""
        mock_super_wb.return_value = {}
        self.stream.is_selected = MagicMock(return_value=False)

        mock_child = MagicMock()
        mock_child.tap_stream_id = "child_stream"
        self.stream.child_to_sync = [mock_child]

        state = {}
        result = self.stream.write_bookmark(state, "parent_stream", value="2021-01-01")

        # Should call super().write_bookmark for the child
        mock_super_wb.assert_called()
        self.assertEqual(result, state)


# ---------------------------------------------------------------------------
# ChildBaseStream
# ---------------------------------------------------------------------------

class TestChildBaseStream(unittest.TestCase):

    def setUp(self):
        self.stream = _make_stream(ConcreteChildStream)

    def test_get_url_endpoint_formats_with_parent_id(self):
        """URL is constructed using the parent object's id."""
        parent_obj = {"id": "parent123"}
        result = self.stream.get_url_endpoint(parent_obj=parent_obj)
        self.assertEqual(
            result,
            "https://www.zohoapis.com/crm/v8/parent/parent123/children"
        )

    @patch('tap_zoho_crm.streams.abstracts.IncrementalStream.get_bookmark', return_value="2021-01-01")
    def test_get_bookmark_caches_on_first_call(self, mock_gb):
        """First call fetches and caches the bookmark value."""
        state = {}
        result = self.stream.get_bookmark(state, "child_stream")
        self.assertEqual(result, "2021-01-01")
        mock_gb.assert_called_once()

    @patch('tap_zoho_crm.streams.abstracts.IncrementalStream.get_bookmark', return_value="2021-01-01")
    def test_get_bookmark_uses_cache_on_subsequent_calls(self, mock_gb):
        """Subsequent calls return cached value without calling super."""
        state = {}
        self.stream.get_bookmark(state, "child_stream")
        self.stream.get_bookmark(state, "child_stream")
        # super().get_bookmark should only be called once
        mock_gb.assert_called_once()
