import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta
from parameterized import parameterized
import requests
from unittest.mock import patch, MagicMock
from requests.exceptions import Timeout, ConnectionError, ChunkedEncodingError
from tap_zoho_crm.client import Client, BASE_API_DOMAIN
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
# Helpers shared by token-chaining tests
# ---------------------------------------------------------------------------

REFRESH_RESPONSE = {
    "access_token": "new_access_token",
    "token_type": "Bearer",
    "api_domain": "https://www.zohoapis.com",
    "scope": "ZohoCRM.modules.ALL",
    "expires_in": 3600,
}


def _make_client(extra_config=None, config_path=None):
    """Return a Client with minimal config and an optionally pre-seeded token."""
    cfg = default_config.copy()
    if extra_config:
        cfg.update(extra_config)
    return Client(cfg, config_path=config_path)


class TestTokenChaining(unittest.TestCase):
    """Unit tests for access-token chaining (reuse / refresh / persist)."""

    # ------------------------------------------------------------------
    # __init__ – loading persisted token from config
    # ------------------------------------------------------------------

    def test_init_loads_valid_token_from_config(self):
        """Client picks up a saved token and expiry from the config dict."""
        future = datetime.now() + timedelta(hours=1)
        cfg = {
            "access_token": "saved_token",
            "token_expires_at": future.isoformat(),
            "token_type": "Bearer",
            "api_domain": "https://www.zohoapis.eu",
        }
        client = _make_client(extra_config=cfg)

        self.assertEqual(client._access_token, "saved_token")
        self.assertEqual(client._token_type, "Bearer")
        self.assertEqual(client._api_domain, "https://www.zohoapis.eu")
        self.assertAlmostEqual(
            client._expires_at.timestamp(), future.timestamp(), delta=1
        )

    def test_init_ignores_malformed_token_expiry(self):
        """A malformed token_expires_at leaves _expires_at as None."""
        cfg = {
            "access_token": "saved_token",
            "token_expires_at": "NOT-A-DATE",
        }
        client = _make_client(extra_config=cfg)
        self.assertIsNone(client._expires_at)

    def test_init_parses_token_expiry_with_trailing_z(self):
        """token_expires_at ending in 'Z' (RFC 3339) is parsed correctly."""
        cfg = {
            "access_token": "saved_token",
            "token_expires_at": "2099-01-01T00:00:00Z",
        }
        client = _make_client(extra_config=cfg)
        self.assertIsNotNone(client._expires_at)
        self.assertEqual(client._expires_at.utcoffset().total_seconds(), 0)

    def test_init_ignores_non_string_token_expiry(self):
        """A non-string token_expires_at (e.g. integer) leaves _expires_at as None."""
        cfg = {
            "access_token": "saved_token",
            "token_expires_at": 1234567890,
        }
        client = _make_client(extra_config=cfg)
        self.assertIsNone(client._expires_at)

    @patch("tap_zoho_crm.client.Client._refresh_access_token")
    def test_enter_does_not_raise_with_tz_aware_expiry(self, mock_refresh):
        """__enter__ does not raise TypeError when _expires_at is timezone-aware."""
        from datetime import timezone
        future = datetime.now(tz=timezone.utc) + timedelta(hours=1)
        cfg = {
            "access_token": "still_valid",
            "token_expires_at": future.isoformat(),
        }
        client = _make_client(extra_config=cfg)
        # Should not raise "can't compare offset-naive and offset-aware datetimes"
        client.__enter__()
        mock_refresh.assert_not_called()

    def test_init_defaults_api_domain_when_absent(self):
        """When api_domain is not in config, BASE_API_DOMAIN is used."""
        client = _make_client()
        self.assertEqual(client._api_domain, BASE_API_DOMAIN)
        self.assertTrue(client.base_url.startswith(BASE_API_DOMAIN))

    # ------------------------------------------------------------------
    # __enter__ – reuse vs refresh decision
    # ------------------------------------------------------------------

    @patch("tap_zoho_crm.client.Client._refresh_access_token")
    def test_enter_reuses_valid_token(self, mock_refresh):
        """__enter__ skips refresh when a valid token is already present."""
        future = datetime.now() + timedelta(hours=1)
        cfg = {
            "access_token": "still_valid",
            "token_expires_at": future.isoformat(),
        }
        client = _make_client(extra_config=cfg)
        client.__enter__()
        mock_refresh.assert_not_called()

    @patch("tap_zoho_crm.client.Client._refresh_access_token")
    def test_enter_refreshes_when_token_missing(self, mock_refresh):
        """__enter__ calls _refresh_access_token when no token is stored."""
        client = _make_client()
        client.__enter__()
        mock_refresh.assert_called_once()

    @patch("tap_zoho_crm.client.Client._refresh_access_token")
    def test_enter_refreshes_when_token_expired(self, mock_refresh):
        """__enter__ calls _refresh_access_token when the stored token is expired."""
        past = datetime.now() - timedelta(seconds=10)
        cfg = {
            "access_token": "expired_token",
            "token_expires_at": past.isoformat(),
        }
        client = _make_client(extra_config=cfg)
        client.__enter__()
        mock_refresh.assert_called_once()

    @patch("tap_zoho_crm.client.Client._refresh_access_token")
    def test_enter_refreshes_when_expires_at_none(self, mock_refresh):
        """__enter__ calls _refresh_access_token when _expires_at is None."""
        cfg = {"access_token": "token_no_expiry"}
        client = _make_client(extra_config=cfg)
        # _expires_at is None because token_expires_at was not in config
        client.__enter__()
        mock_refresh.assert_called_once()

    # ------------------------------------------------------------------
    # _refresh_access_token – updates internal state and persists
    # ------------------------------------------------------------------

    @patch("tap_zoho_crm.client.Client._save_token_to_config")
    @patch("tap_zoho_crm.client.Client.make_request", return_value=REFRESH_RESPONSE)
    def test_refresh_updates_internal_state(self, mock_req, mock_save):
        """_refresh_access_token stores new token, expiry, domain, and type."""
        client = _make_client()
        client._refresh_access_token()

        self.assertEqual(client._access_token, "new_access_token")
        self.assertEqual(client._token_type, "Bearer")
        self.assertEqual(client._api_domain, "https://www.zohoapis.com")
        self.assertIsNotNone(client._expires_at)
        self.assertGreater(client._expires_at, datetime.now())

    @patch("tap_zoho_crm.client.Client._save_token_to_config")
    @patch("tap_zoho_crm.client.Client.make_request", return_value=REFRESH_RESPONSE)
    def test_refresh_calls_save(self, mock_req, mock_save):
        """_refresh_access_token must call _save_token_to_config."""
        client = _make_client()
        client._refresh_access_token()
        mock_save.assert_called_once()

    @patch("tap_zoho_crm.client.Client._save_token_to_config")
    @patch("tap_zoho_crm.client.Client.make_request", return_value={**REFRESH_RESPONSE, "api_domain": "https://www.zohoapis.eu"})
    def test_refresh_updates_base_url_on_domain_change(self, mock_req, mock_save):
        """base_url is updated when api_domain changes during refresh."""
        client = _make_client()
        client._refresh_access_token()
        self.assertEqual(client._api_domain, "https://www.zohoapis.eu")
        self.assertEqual(client.base_url, "https://www.zohoapis.eu/crm/v8")

    @patch("tap_zoho_crm.client.Client._save_token_to_config")
    @patch("tap_zoho_crm.client.Client.make_request", return_value={k: v for k, v in REFRESH_RESPONSE.items() if k != "api_domain"})
    def test_refresh_keeps_existing_domain_when_absent_in_response(self, mock_req, mock_save):
        """base_url is unchanged when api_domain is absent from token response."""
        client = _make_client()
        client._api_domain = "https://www.zohoapis.eu"
        client._refresh_access_token()
        self.assertEqual(client._api_domain, "https://www.zohoapis.eu")

    # ------------------------------------------------------------------
    # _save_token_to_config
    # ------------------------------------------------------------------

    def test_save_token_writes_correct_fields(self):
        """_save_token_to_config writes access_token, expiry, type, domain."""
        future = datetime.now() + timedelta(hours=1)
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as fh:
            json.dump(default_config.copy(), fh)
            tmp_path = fh.name

        try:
            client = _make_client(config_path=tmp_path)
            client._access_token = "saved_token"
            client._expires_at = future
            client._token_type = "Bearer"
            client._api_domain = "https://www.zohoapis.com"
            client._save_token_to_config()

            with open(tmp_path) as fh:
                saved = json.load(fh)

            self.assertEqual(saved["access_token"], "saved_token")
            self.assertEqual(saved["token_expires_at"], future.isoformat())
            self.assertEqual(saved["token_type"], "Bearer")
            self.assertEqual(saved["api_domain"], "https://www.zohoapis.com")
        finally:
            os.unlink(tmp_path)

    def test_save_token_no_op_when_config_path_absent(self):
        """_save_token_to_config does nothing when config_path is None."""
        client = _make_client(config_path=None)
        client._access_token = "token"
        client._expires_at = datetime.now() + timedelta(hours=1)
        # Should complete without raising even though there is no file
        client._save_token_to_config()

    def test_save_token_logs_warning_on_io_error(self):
        """_save_token_to_config logs a warning when the file cannot be written."""
        client = _make_client(config_path="/nonexistent/path/config.json")
        client._access_token = "token"
        client._expires_at = datetime.now() + timedelta(hours=1)
        client._token_type = "Bearer"
        # Should not raise — just log a warning
        client._save_token_to_config()

    # ------------------------------------------------------------------
    # get_access_token – lazy refresh
    # ------------------------------------------------------------------

    @patch("tap_zoho_crm.client.Client._refresh_access_token")
    def test_get_access_token_returns_cached_token(self, mock_refresh):
        """get_access_token returns the cached token without refreshing."""
        future = datetime.now() + timedelta(hours=1)
        cfg = {"access_token": "cached", "token_expires_at": future.isoformat()}
        client = _make_client(extra_config=cfg)
        token = client.get_access_token()
        self.assertEqual(token, "cached")
        mock_refresh.assert_not_called()

    @patch("tap_zoho_crm.client.Client._refresh_access_token")
    def test_get_access_token_refreshes_when_expired(self, mock_refresh):
        """get_access_token triggers refresh when _expires_at is in the past."""
        past = datetime.now() - timedelta(seconds=10)
        cfg = {"access_token": "old_token", "token_expires_at": past.isoformat()}
        client = _make_client(extra_config=cfg)

        def set_new_token():
            client._access_token = "fresh_token"
            client._expires_at = datetime.now() + timedelta(hours=1)

        mock_refresh.side_effect = set_new_token
        token = client.get_access_token()
        mock_refresh.assert_called_once()
        self.assertEqual(token, "fresh_token")

    # ------------------------------------------------------------------
    # make_request – mid-sync 401 retry
    # ------------------------------------------------------------------

    @patch("tap_zoho_crm.client.Client._refresh_access_token")
    @patch("tap_zoho_crm.client.Client._Client__make_request")
    def test_make_request_retries_on_401(self, mock_inner, mock_refresh):
        """make_request catches ZohoCRMUnauthorizedError, refreshes, and retries."""
        mock_response = MagicMock()
        mock_response.status_code = 401

        # First call raises 401; second call succeeds
        mock_inner.side_effect = [
            ZohoCRMUnauthorizedError("401", mock_response),
            {"data": "ok"},
        ]

        client = _make_client()
        client._access_token = "old_token"
        client._expires_at = datetime.now() + timedelta(hours=1)
        client._token_type = "Bearer"
        client.authenticate = MagicMock(return_value=({"Authorization": "Bearer new"}, {}))

        result = client.make_request("GET", "https://api.example.com/resource")

        self.assertEqual(result, {"data": "ok"})
        mock_refresh.assert_called_once()
        self.assertEqual(mock_inner.call_count, 2)

    @patch("tap_zoho_crm.client.Client._refresh_access_token")
    @patch("tap_zoho_crm.client.Client._Client__make_request")
    def test_make_request_does_not_retry_401_on_non_auth_request(self, mock_inner, mock_refresh):
        """401 on a non-authenticated request (is_auth_req=False) is re-raised immediately."""
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_inner.side_effect = ZohoCRMUnauthorizedError("401", mock_response)

        client = _make_client()

        with self.assertRaises(ZohoCRMUnauthorizedError):
            client.make_request(
                "POST",
                "https://accounts.zoho.com/oauth/v2/token",
                is_auth_req=False,
            )

        mock_refresh.assert_not_called()
        self.assertEqual(mock_inner.call_count, 1)

    @patch("tap_zoho_crm.client.Client._refresh_access_token")
    @patch("tap_zoho_crm.client.Client._Client__make_request")
    def test_make_request_propagates_401_on_retry_failure(self, mock_inner, mock_refresh):
        """If the retried request also returns 401 it propagates to the caller."""
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_inner.side_effect = ZohoCRMUnauthorizedError("401", mock_response)

        client = _make_client()
        client._access_token = "old_token"
        client._expires_at = datetime.now() + timedelta(hours=1)
        client._token_type = "Bearer"
        client.authenticate = MagicMock(return_value=({"Authorization": "Bearer new"}, {}))

        with self.assertRaises(ZohoCRMUnauthorizedError):
            client.make_request("GET", "https://api.example.com/resource")

        # First attempt + one retry = 2 calls; refresh attempted once
        self.assertEqual(mock_inner.call_count, 2)
        mock_refresh.assert_called_once()
