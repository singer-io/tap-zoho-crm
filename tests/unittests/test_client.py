import unittest
from parameterized import parameterized
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
    def __init__(
            self,
            status_code,
            resp="",
            content=[""],
            headers=None,
            raise_error=True,
            text={}
        ):
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


class TestClient(unittest.TestCase):

    @parameterized.expand([
        ["empty string", "", 300.0],
        ["string value", "12", 12.0],
        ["int value", 10, 10.0],
        ["float value", 20.0, 20.0],
        ["zero value", 0, 300.0]
    ])
    @patch("tap_zoho_crm.client.session")
    def test_client_initialization(self, name, input_value, expected_value, mock_session):
        """
        Test that the Client initializes the request_timeout attribute correctly from the config,
        and that it uses the 'session' object properly for HTTP requests.
        """
        config = default_config.copy()
        config["request_timeout"] = input_value
        client = Client(config)
        self.assertEqual(client.request_timeout, expected_value)
        self.assertIsInstance(client._session, mock_session().__class__)

    @parameterized.expand([
        ["GET request", "GET"],
        ["POST request", "POST"],
    ])
    @patch("tap_zoho_crm.client.Client._Client__make_request", return_value={"data": "ok"})
    def test_client_make_request_mocked(self, name, method, mock_make_request):
        """
        Test that make_request returns data and calls __make_request correctly
        for both GET and POST methods.
        """
        client = Client(default_config)
        client.authenticate = MagicMock(return_value=({'Authorization': 'Bearer test'}, {'page': 1}))
        result = client.make_request(method, "https://api.example.com/resource", headers={})
        self.assertEqual(result, {"data": "ok"})
        mock_make_request.assert_called_once()

    @parameterized.expand([
        [
            "400 BadRequest",
            400,
            MockResponse(400, text={"message": "A validation exception has occurred."}),
            ZohoCRMBadRequestError,
            "A validation exception has occurred."
        ],
        [
            "401 Unauthorized",
            401,
            MockResponse(401, text={"message": "The access token provided is expired, revoked, malformed or invalid for other reasons."}),
            ZohoCRMUnauthorizedError,
            "The access token provided is expired, revoked, malformed or invalid for other reasons."
        ]
    ])
    def test_make_request_errors_without_retry(self, name, status_code, mock_resp, expected_exception, expected_message):
        """
        Test that __make_request raises correct exceptions for error codes without retry logic
        """
        client = Client(default_config)

        with patch.object(client._session, "request", return_value=mock_resp):
            with self.assertRaises(expected_exception) as context:
                client._Client__make_request("GET", "https://api.example.com/resource")

        self.assertIn(expected_message, str(context.exception))

    @parameterized.expand([
        ["ConnectionError", ConnectionError],
        ["Timeout", Timeout],
        ["ChunkedEncodingError", ChunkedEncodingError],
        ["RateLimitError", ZohoCRMRateLimitError],
        ["InternalServerError", ZohoCRMInternalServerError],
    ])
    def test_make_request_with_retry_on_connection_errors(self, name, exception_type):
        """
        Test that __make_request retries up to 5 times for retryable exceptions
        """
        client = Client(default_config)

        with patch.object(client._session, "request", side_effect=exception_type) as mock_request:
            with patch("time.sleep", return_value=None):
                with self.assertRaises(exception_type):
                    client._Client__make_request("GET", "https://api.example.com/resource")

        self.assertEqual(mock_request.call_count, 5)

