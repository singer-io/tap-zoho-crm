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


# ---------------------------------------------------------------------------
# Additional tests to cover previously uncovered paths
# ---------------------------------------------------------------------------

class TestMockResponseRaiseForStatus(unittest.TestCase):
    """Exercise MockResponse.raise_for_status() paths (covers test file's own lines)."""

    def test_raise_for_status_returns_status_code_when_no_error(self):
        resp = MockResponse(200, raise_error=False)
        result = resp.raise_for_status()
        self.assertEqual(result, 200)

    def test_raise_for_status_raises_http_error(self):
        resp = MockResponse(400, raise_error=True)
        with self.assertRaises(requests.HTTPError):
            resp.raise_for_status()


class TestRaiseForErrorPaths(unittest.TestCase):
    """Tests for raise_for_error() branches not covered by existing tests."""

    def test_raise_for_error_returns_none_for_200(self):
        """200 OK → returns early without raising."""
        from tap_zoho_crm.client import raise_for_error
        resp = MockResponse(200, text={"data": "ok"})
        # Should not raise
        result = raise_for_error(resp)
        self.assertIsNone(result)

    def test_raise_for_error_returns_none_for_204(self):
        """204 No Content → returns early without raising."""
        from tap_zoho_crm.client import raise_for_error
        resp = MockResponse(204, text={})
        result = raise_for_error(resp)
        self.assertIsNone(result)

    def test_raise_for_error_returns_none_for_304(self):
        """304 Not Modified is a successful empty incremental response."""
        from tap_zoho_crm.client import raise_for_error
        resp = MockResponse(304, text={})
        result = raise_for_error(resp)
        self.assertIsNone(result)

    def test_raise_for_error_handles_json_decode_failure(self):
        """When response.json() raises, falls back to empty dict for error parsing."""
        from tap_zoho_crm.client import raise_for_error
        from tap_zoho_crm.exceptions import ZohoCRMBadRequestError

        resp = MagicMock()
        resp.status_code = 400
        resp.json.side_effect = ValueError("No JSON")

        with self.assertRaises(ZohoCRMBadRequestError):
            raise_for_error(resp)

    def test_raise_for_error_skips_oauth_scope_mismatch(self):
        """401 OAUTH_SCOPE_MISMATCH → logs and returns None without raising."""
        from tap_zoho_crm.client import raise_for_error

        resp = MockResponse(401, text={
            "code": "OAUTH_SCOPE_MISMATCH",
            "message": "scope mismatch",
            "status": "success"
        })
        result = raise_for_error(resp)
        self.assertIsNone(result)

    def test_raise_for_error_skips_feature_not_enabled(self):
        """400 FEATURE_NOT_ENABLED → logs and returns None without raising."""
        from tap_zoho_crm.client import raise_for_error

        resp = MockResponse(400, text={
            "code": "FEATURE_NOT_ENABLED",
            "message": "feature not enabled",
            "status": "success"
        })
        result = raise_for_error(resp)
        self.assertIsNone(result)

    def test_raise_for_error_handles_error_status_in_body(self):
        """When response body has status='error', message uses error-specific format."""
        from tap_zoho_crm.client import raise_for_error
        from tap_zoho_crm.exceptions import ZohoCRMNotFoundError

        resp = MockResponse(404, text={
            "code": "SOME_CODE",
            "message": "not found detail",
            "status": "error"
        })
        with self.assertRaises(ZohoCRMNotFoundError):
            raise_for_error(resp)

    def test_raise_for_error_retryable_access_denied(self):
        """400 ACCESS DENIED with the specific too-many-requests description → rate limit error."""
        from tap_zoho_crm.client import raise_for_error
        from tap_zoho_crm.exceptions import ZohoCRMRateLimitError

        # headers must be a dict so ZohoCRMRateLimitError.__init__ can call headers.get()
        resp = MockResponse(400, headers={}, text={
            "error": "ACCESS DENIED",
            "error_description": "too many requests continuously. please try again after some time.",
            "status": "error"
        })
        with self.assertRaises(ZohoCRMRateLimitError):
            raise_for_error(resp)


class TestWaitIfRetryAfter(unittest.TestCase):
    """Tests for wait_if_retry_after() backoff handler."""

    def test_sleeps_when_retry_after_is_set(self):
        from tap_zoho_crm.client import wait_if_retry_after

        exc = MagicMock()
        exc.retry_after = 5
        details = {'exception': exc}

        with patch('tap_zoho_crm.client.time.sleep') as mock_sleep:
            wait_if_retry_after(details)

        mock_sleep.assert_called_once_with(5)

    def test_does_not_sleep_when_retry_after_is_none(self):
        from tap_zoho_crm.client import wait_if_retry_after

        exc = MagicMock()
        exc.retry_after = None
        details = {'exception': exc}

        with patch('tap_zoho_crm.client.time.sleep') as mock_sleep:
            wait_if_retry_after(details)

        mock_sleep.assert_not_called()

    def test_does_not_sleep_when_no_retry_after_attribute(self):
        from tap_zoho_crm.client import wait_if_retry_after

        exc = Exception("plain error")  # no retry_after attribute
        details = {'exception': exc}

        with patch('tap_zoho_crm.client.time.sleep') as mock_sleep:
            wait_if_retry_after(details)

        mock_sleep.assert_not_called()


class TestClientRefreshAccessToken(unittest.TestCase):
    """Tests for Client._refresh_access_token()."""

    @patch('tap_zoho_crm.client.Client._Client__make_request')
    def test_refresh_access_token_sets_token_attributes(self, mock_make_request):
        """_refresh_access_token sets _access_token, _scope, _api_domain etc."""
        mock_make_request.return_value = {
            "access_token": "new_token_123",
            "scope": "ZohoCRM.modules.ALL",
            "api_domain": "https://www.zohoapis.com",
            "token_type": "Bearer",
            "expires_in": 3600
        }

        client = Client(default_config)
        client._refresh_access_token()

        self.assertEqual(client._access_token, "new_token_123")
        self.assertEqual(client._token_type, "Bearer")
        self.assertIsNotNone(client._expires_at)

    @patch('tap_zoho_crm.client.Client._Client__make_request')
    def test_refresh_access_token_defaults_bearer_token_type(self, mock_make_request):
        """When token_type is absent from response, defaults to 'Bearer'."""
        mock_make_request.return_value = {
            "access_token": "tok",
            "scope": "scope",
            "api_domain": "https://www.zohoapis.com",
            "expires_in": 3600
            # no token_type
        }
        client = Client(default_config)
        client._refresh_access_token()
        self.assertEqual(client._token_type, "Bearer")


class TestClientGetAccessToken(unittest.TestCase):
    """Tests for Client.get_access_token()."""

    @patch('tap_zoho_crm.client.Client._refresh_access_token')
    def test_returns_cached_token_when_not_expired(self, mock_refresh):
        """Returns existing token without refreshing when it hasn't expired."""
        from datetime import datetime, timedelta
        client = Client(default_config)
        client._access_token = "existing_token"
        client._expires_at = datetime.now() + timedelta(seconds=3600)

        token = client.get_access_token()

        self.assertEqual(token, "existing_token")
        mock_refresh.assert_not_called()

    @patch('tap_zoho_crm.client.Client._refresh_access_token')
    def test_refreshes_when_token_is_none(self, mock_refresh):
        """Calls _refresh_access_token when _access_token is None."""
        client = Client(default_config)
        client._access_token = None
        mock_refresh.side_effect = lambda: setattr(client, '_access_token', 'refreshed')

        token = client.get_access_token()

        mock_refresh.assert_called_once()
        self.assertEqual(token, 'refreshed')


class TestClientHeadersAndAuthenticate(unittest.TestCase):
    """Tests for Client.headers property and Client.authenticate()."""

    def test_headers_returns_dict_with_user_agent_and_content_type(self):
        client = Client(default_config)
        headers = client.headers
        self.assertEqual(headers['User-Agent'], default_config['user_agent'])
        self.assertEqual(headers['Content-Type'], 'application/json')

    @patch('tap_zoho_crm.client.Client.get_access_token', return_value='tok_abc')
    def test_authenticate_with_empty_headers_removes_content_type(self, mock_get_token):
        """When headers arg is empty/falsy, Content-Type is removed from result."""
        client = Client(default_config)
        client._token_type = "Bearer"

        result_headers, result_params = client.authenticate({}, {})

        self.assertNotIn('Content-Type', result_headers)
        self.assertIn('Authorization', result_headers)

    @patch('tap_zoho_crm.client.Client.get_access_token', return_value='tok_abc')
    def test_authenticate_with_custom_headers_merges_them(self, mock_get_token):
        """Custom headers are merged into the result."""
        client = Client(default_config)
        client._token_type = "Bearer"

        custom_headers = {'X-Custom': 'value'}
        result_headers, _ = client.authenticate(custom_headers, {})

        self.assertEqual(result_headers['X-Custom'], 'value')
        self.assertIn('Authorization', result_headers)


class TestMakeRequestNoAuth(unittest.TestCase):
    """Tests for make_request with is_auth_req=False."""

    @patch('tap_zoho_crm.client.Client._Client__make_request', return_value={"ok": True})
    def test_make_request_skips_authenticate_when_not_auth_req(self, mock_inner):
        """When is_auth_req=False, authenticate() is not called."""
        client = Client(default_config)
        client.authenticate = MagicMock()

        client.make_request("GET", "https://example.com/api", is_auth_req=False)

        client.authenticate.assert_not_called()

    @patch('tap_zoho_crm.client.Client._Client__make_request', return_value={"ok": True})
    def test_make_request_uses_path_when_endpoint_is_none(self, mock_inner):
        """When endpoint is None/empty, URL is built from base_url + path."""
        client = Client(default_config)
        client.authenticate = MagicMock(return_value=({}, {}))

        client.make_request("GET", endpoint=None, path="contacts", is_auth_req=False)

        call_args = mock_inner.call_args
        endpoint_used = call_args[0][1]  # second positional arg is endpoint
        self.assertIn("contacts", endpoint_used)


class TestMakeRequestInnerBehavior(unittest.TestCase):
    """Tests for Client.__make_request internals."""

    def test_returns_empty_dict_for_204_response(self):
        """204 No Content → returns empty dict."""
        client = Client(default_config)
        resp = MockResponse(204, text={})
        resp.status_code = 204

        with patch.object(client._session, "request", return_value=resp):
            result = client._Client__make_request("GET", "https://example.com/api")

        self.assertEqual(result, {})

    def test_returns_empty_dict_for_304_response(self):
        """304 Not Modified → returns empty dict."""
        client = Client(default_config)
        resp = MockResponse(304, text={})

        with patch.object(client._session, "request", return_value=resp):
            result = client._Client__make_request("GET", "https://api.example.com/resource")

        self.assertEqual(result, {})

    def test_raises_value_error_for_unsupported_method(self):
        """Unsupported HTTP method raises ValueError."""
        client = Client(default_config)

        with self.assertRaises(ValueError) as ctx:
            client._Client__make_request("DELETE", "https://example.com/api")

        self.assertIn("Unsupported method", str(ctx.exception))


class TestZohoCRMRateLimitErrorInit(unittest.TestCase):
    """Tests for ZohoCRMRateLimitError.__init__ try/except (lines 49-52)."""

    def test_retry_after_parsed_from_response_header(self):
        """retry_after is read from the Retry-After header."""
        from tap_zoho_crm.exceptions import ZohoCRMRateLimitError
        mock_response = MagicMock()
        mock_response.headers.get.return_value = "30"

        error = ZohoCRMRateLimitError("Too many requests", response=mock_response)
        self.assertEqual(error.retry_after, 30)

    def test_retry_after_defaults_to_60_on_invalid_header(self):
        """When Retry-After header is non-integer, retry_after defaults to 60."""
        from tap_zoho_crm.exceptions import ZohoCRMRateLimitError
        mock_response = MagicMock()
        mock_response.headers.get.return_value = "not-a-number"

        error = ZohoCRMRateLimitError("Too many requests", response=mock_response)
        self.assertEqual(error.retry_after, 60)

    def test_retry_after_is_none_when_no_response(self):
        """When response is None, retry_after stays None."""
        from tap_zoho_crm.exceptions import ZohoCRMRateLimitError
        error = ZohoCRMRateLimitError("Too many requests", response=None)
        self.assertIsNone(error.retry_after)
