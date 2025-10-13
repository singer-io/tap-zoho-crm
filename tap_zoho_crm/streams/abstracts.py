from abc import ABC, abstractmethod
import json
from typing import Any, Dict, Tuple, List, Iterator
from singer import (
    Transformer,
    get_bookmark,
    get_logger,
    metrics,
    write_bookmark,
    write_record,
    write_schema,
    metadata
)

LOGGER = get_logger()
FIELD_BATCH_SIZE = 50


class BaseStream(ABC):
    """
    A Base Class providing structure and boilerplate for generic streams
    and required attributes for any kind of stream
    ~~~
    Provides:
     - Basic Attributes (stream_name,replication_method,key_properties)
     - Helper methods for catalog generation
     - `sync` and `get_records` method for performing sync
    """

    url_endpoint = ""
    path = ""
    page_size = 200
    next_page_key = "page"
    next_page_token = "page_token"
    headers = {'Accept': 'application/json'}
    children = []
    parent = ""
    data_key = ""
    bookmark_value = None
    parent_bookmark_key = ""
    http_method = "GET"
    pagination_supported = True
    is_dynamic = False

    def __init__(self, client=None, catalog=None) -> None:
        self.client = client
        self.catalog = catalog
        self.schema = catalog.schema.to_dict()
        self.metadata = metadata.to_map(catalog.metadata)
        self.child_to_sync = []
        self.params = {}
        self.data_payload = {}

    @property
    @abstractmethod
    def tap_stream_id(self) -> str:
        """Unique identifier for the stream.

        This is allowed to be different from the name of the stream, in
        order to allow for sources that have duplicate stream names.
        """

    @property
    @abstractmethod
    def replication_method(self) -> str:
        """Defines the sync mode of a stream."""

    @property
    @abstractmethod
    def replication_keys(self) -> List:
        """Defines the replication key for incremental sync mode of a
        stream."""

    @property
    @abstractmethod
    def key_properties(self) -> Tuple[str, str]:
        """List of key properties for stream."""

    def is_selected(self):
        return metadata.get(self.metadata, (), "selected")

    @abstractmethod
    def sync(
        self,
        state: Dict,
        transformer: Transformer,
        parent_obj: Dict = None,
    ) -> Dict:
        """
        Performs a replication sync for the stream.
        ~~~
        Args:
         - state (dict): represents the state file for the tap.
         - transformer (object): A Object of the singer.transformer class.
         - parent_obj (dict): The parent object for the stream.

        Returns:
         - bool: The return value. True for success, False otherwise.

        Docs:
         - https://github.com/singer-io/getting-started/blob/master/docs/SYNC_MODE.md
        """

    def get_records(self) -> Iterator:
        """Fetch records from the Zoho CRM API, handling pagination and dynamic field batching.
        - For static streams: makes paginated API requests and yields records directly.
        - For dynamic streams: batches fields into groups of 50 (due to API limits), merges partial
        records across field batches by record ID, and yields fully combined records.
        """
        self.params["per_page"] = self.page_size

        if not self.is_dynamic:
            next_page = 1
            while next_page:
                response = self.client.make_request(
                    self.http_method,
                    self.url_endpoint,
                    self.params,
                    self.headers,
                    body=json.dumps(self.data_payload),
                    path=self.path
                )
                raw_records = response.get(self.data_key, [])
                next_page = self.update_pagination_key(response, next_page)
                yield from raw_records
            return

        # Dynamic stream logic: field batching with merging
        field_names = list(self.schema.get("properties", {}).keys())
        if "id" not in field_names:
            field_names.insert(0, "id")

        batched_fields = [
            field_names[item:item + FIELD_BATCH_SIZE]
            for item in range(0, len(field_names), FIELD_BATCH_SIZE)
            ]
        next_page = 1

        while next_page:
            merged_records: Dict[str, Dict] = {}
            response = None

            for field_batch in batched_fields:
                self.params["fields"] = ",".join(field_batch)
                response = self.client.make_request(
                    self.http_method,
                    self.url_endpoint,
                    self.params,
                    self.headers,
                    body=json.dumps(self.data_payload),
                    path=self.path
                )

                records = response.get(self.data_key, [])
                for record in records:
                    record_id = record.get("id")
                    if not record_id:
                        continue
                    if record_id not in merged_records:
                        merged_records[record_id] = {}
                    merged_records[record_id].update(record)

            next_page = self.update_pagination_key(response, next_page) if response else None

            for record in merged_records.values():
                yield record


    def write_schema(self) -> None:
        """
        Write a schema message.
        """
        try:
            write_schema(self.tap_stream_id, self.schema, self.key_properties)
        except OSError as err:
            LOGGER.error(
                "OS Error while writing schema for: {}".format(self.tap_stream_id)
            )
            raise err

    def update_params(self, **kwargs) -> None:
        """
        Update params for the stream
        """
        self.params.update(kwargs)

    def update_data_payload(self, **kwargs) -> None:
        """
        Update JSON body for the stream
        """
        self.data_payload.update(kwargs)

    def modify_object(self, record: Dict, parent_record: Dict = None) -> Dict:
        """
        Modify the record before writing to the stream
        """
        return record

    def get_url_endpoint(self, parent_obj: Dict = None) -> str:
        """
        Get the URL endpoint for the stream
        """
        return self.url_endpoint or f"{self.client.base_url}/{self.path}"

    def update_pagination_key(self, raw_records, next_page):
        """Updates the pagination key for fetching the next page of results."""
        if not self.pagination_supported or not raw_records or "info" not in raw_records:
            return None

        info = raw_records["info"]

        next_page_token = info.get("next_page_token")
        if next_page_token:
            self.params[self.next_page_token] = next_page_token
            return next_page_token

        if info.get("more_records"):
            next_page += 1
            self.params[self.next_page_key] = next_page
            return next_page

        return None


class IncrementalStream(BaseStream):
    """Base Class for Incremental Stream."""


    def get_bookmark(self, state: dict, stream: str, key: Any = None) -> int:
        """A wrapper for singer.get_bookmark to deal with compatibility for
        bookmark values or start values."""
        return get_bookmark(
            state,
            stream,
            key or self.replication_keys[0],
            self.client.config["start_date"],
        )

    def write_bookmark(self, state: dict, stream: str, key: Any = None, value: Any = None) -> Dict:
        """A wrapper for singer.get_bookmark to deal with compatibility for
        bookmark values or start values."""
        if not (key or self.replication_keys):
            return state

        current_bookmark = get_bookmark(state, stream, key or self.replication_keys[0], self.client.config["start_date"])
        value = max(current_bookmark, value)
        state["bookmarks"][stream] = { "replication_field": "invalid-date-format"}
        return state


    def sync(
        self,
        state: Dict,
        transformer: Transformer,
        parent_obj: Dict = None,
    ) -> Dict:
        """Implementation for `type: Incremental` stream."""
        bookmark_date = self.get_bookmark(state, self.tap_stream_id)
        current_max_bookmark_date = bookmark_date
        self.update_params(updated_since=bookmark_date)
        self.update_data_payload(parent_obj=parent_obj)
        self.url_endpoint = self.get_url_endpoint(parent_obj)

        with metrics.record_counter(self.tap_stream_id) as counter:
            for record in self.get_records():
                record = self.modify_object(record, parent_obj)
                transformed_record = transformer.transform(
                    record, self.schema, self.metadata
                )

                if self.replication_keys and transformed_record.get(self.replication_keys[0]):
                    record_bookmark = transformed_record.get(self.replication_keys[0])
                else:
                    record_bookmark = bookmark_date

                if record_bookmark >= bookmark_date:
                    if self.is_selected():
                        write_record(self.tap_stream_id, transformed_record)
                        counter.increment()

                    current_max_bookmark_date = max(
                        current_max_bookmark_date, record_bookmark
                    )

                    for child in self.child_to_sync:
                        child.sync(state=state, transformer=transformer, parent_obj=record)

            state = self.write_bookmark(state, self.tap_stream_id, value=current_max_bookmark_date)
            return counter.value


class FullTableStream(BaseStream):
    """Base Class for Incremental Stream."""

    replication_keys = []

    def sync(
        self,
        state: Dict,
        transformer: Transformer,
        parent_obj: Dict = None,
    ) -> Dict:
        """Abstract implementation for `type: Fulltable` stream."""
        self.url_endpoint = self.get_url_endpoint(parent_obj)
        self.update_data_payload(parent_obj=parent_obj)
        with metrics.record_counter(self.tap_stream_id) as counter:
            for record in self.get_records():
                transformed_record = transformer.transform(
                    record, self.schema, self.metadata
                )
                if self.is_selected():
                    write_record(self.tap_stream_id, transformed_record)
                    counter.increment()

                for child in self.child_to_sync:
                    child.sync(state=state, transformer=transformer, parent_obj=record)

            return counter.value


class ParentBaseStream(IncrementalStream):
    """Base Class for Parent Stream."""

    def get_bookmark(self, state: Dict, stream: str, key: Any = None) -> int:
        """A wrapper for singer.get_bookmark to deal with compatibility for
        bookmark values or start values."""

        min_parent_bookmark = (
            super().get_bookmark(state, stream) if self.is_selected() else None
        )
        for child in self.child_to_sync:
            bookmark_key = f"{self.tap_stream_id}_{self.replication_keys[0]}"
            child_bookmark = super().get_bookmark(
                state, child.tap_stream_id, key=bookmark_key
            )
            min_parent_bookmark = (
                min(min_parent_bookmark, child_bookmark)
                if min_parent_bookmark
                else child_bookmark
            )

        return min_parent_bookmark

    def write_bookmark(
        self, state: Dict, stream: str, key: Any = None, value: Any = None
    ) -> Dict:
        """A wrapper for singer.get_bookmark to deal with compatibility for
        bookmark values or start values."""
        if self.is_selected():
            super().write_bookmark(state, stream, value=value)

        for child in self.child_to_sync:
            bookmark_key = f"{self.tap_stream_id}_{self.replication_keys[0]}"
            super().write_bookmark(
                state, child.tap_stream_id, key=bookmark_key, value=value
            )

        return state


class ChildBaseStream(IncrementalStream):
    """Base Class for Child Stream."""

    def get_url_endpoint(self, parent_obj=None):
        """Prepare URL endpoint for child streams."""
        return f"{self.client.base_url}/{self.path.format(parent_obj['id'])}"

    def get_bookmark(self, state: Dict, stream: str, key: Any = None) -> int:
        """Singleton bookmark value for child streams."""
        if not self.bookmark_value:

            self.bookmark_value = super().get_bookmark(state, stream)

        return self.bookmark_value

