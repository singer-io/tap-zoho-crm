import pytest
import requests
from unittest.mock import patch, MagicMock
from requests.exceptions import Timeout, ConnectionError, ChunkedEncodingError
from tap_zoho_crm.client import Client
from tap_zoho_crm.exceptions import (
    ZohoCRMBadRequestError,
    ZohoCRMUnauthorizedError,
    ZohoCRMRateLimitError,
    ZohoCRMInternalServerError
)


default_config = {
    "base_url": "https://api.example.com",
    "request_timeout": 30,
    "client_id": "dummy_id",
    "client_secret": "dummy_secret",
    "version": "dummy-version",
    "refresh_token": "dummy_token",
    "user_agent": "test-account <test-email>"
}

class MockResponse:
    def __init__(self, status_code, resp="", content=[""], headers=None, raise_error=True, text={}):
        self.json_data = resp
        self.status_code = status_code
        self.content = content
        self.headers = headers
        self.raise_error = raise_error
        self.text = text
        self.reason = "error"

    def raise_for_status(self):
        if not self.raise_error:
            return self.status_code
        raise requests.HTTPError("mock sample message")

    def json(self):
        return self.text

@pytest.mark.parametrize(
    "input_value,expected_value",
    [
        ("", 300.0),
        ("12", 12.0),
        (10, 10.0),
        (20.0, 20.0),
        (0, 300.0)
    ],
    ids=["empty string", "string value", "int value", "float value", "zero value"]
)
@patch("tap_zoho_crm.client.session")
def test_client_initialization(mock_session, input_value, expected_value):
    """Test the Client initializes request_timeout correctly based on config."""
    default_config["request_timeout"] = input_value
    client = Client(default_config)
    assert client.request_timeout == expected_value
    assert isinstance(client._session, mock_session().__class__)


@pytest.mark.parametrize(
    "method",
    ["GET", "POST"],
    ids=["GET request", "POST request"]
)
@patch("tap_zoho_crm.client.Client._Client__make_request", return_value={"data": "ok"})
def test_client_make_request_mocked(mock_make_request, method):
    """Test that make_request returns data and calls __make_request correctly
        for both GET and POST methods.
    """
    client = Client(default_config)
    client.authenticate = MagicMock(return_value=({'Authorization': 'Bearer test'}, {'page': 1}))
    result = client.make_request(method, "https://api.example.com/resource", headers={})
    assert result == {"data": "ok"}
    mock_make_request.assert_called_once()


@pytest.mark.parametrize(
    "error_code, mock_resp, expected_exception, expected_message",
    [
        (
            400,
            MockResponse(400, text={"message": "A validation exception has occurred."}),
            ZohoCRMBadRequestError,
            "A validation exception has occurred."
        ),
        (
            401,
            MockResponse(401, text={"message": "The access token provided is expired, revoked, malformed or invalid for other reasons."}),
            ZohoCRMUnauthorizedError,
            "The access token provided is expired, revoked, malformed or invalid for other reasons."
        )
    ],
    ids=["400 BadRequest", "401 Unauthorized"]
)
def test_make_request_errors_without_retry(error_code, mock_resp, expected_exception, expected_message):
    """
    Test that __make_request raises correct exceptions for error codes without retry logic.
    """
    client = Client(default_config)

    with patch.object(client._session, "request", return_value=mock_resp):
        with pytest.raises(expected_exception) as e:
            client._Client__make_request("GET", "https://api.example.com/resource")

    assert expected_message in str(e.value)


@pytest.mark.parametrize(
    "exception_type",
    [ConnectionError, Timeout, ChunkedEncodingError, ZohoCRMRateLimitError, ZohoCRMInternalServerError],
    ids=["ConnectionError", "Timeout", "ChunkedEncodingError", "RateLimitError", "InternalServerError"]
)
def test_make_request_with_retry_on_connection_errors(exception_type):
    """Test that __make_request retries up to 5 times for retryable exceptions."""
    client = Client(default_config)

    with patch.object(client._session, "request", side_effect=exception_type) as mock_request:
        with patch("time.sleep"):  # Prevent actual sleep
            with pytest.raises(exception_type):
                client._Client__make_request("GET", "https://api.example.com/resource")

    assert mock_request.call_count == 5

