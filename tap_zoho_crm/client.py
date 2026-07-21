from typing import Any, Dict, Mapping, Optional, Tuple
from datetime import datetime, timedelta
import json

import backoff
import requests
from requests import session
from requests.exceptions import Timeout, ConnectionError, ChunkedEncodingError
from singer import get_logger, metrics

from tap_zoho_crm.exceptions import (
    ERROR_CODE_EXCEPTION_MAPPING,
    ZohoCRMError,
    ZohoCRMRateLimitError,
    ZohoCRMUnauthorizedError,
    ZohoCRMInternalServerError,
    ZohoCRMServiceUnavailableError
)

LOGGER = get_logger()
REQUEST_TIMEOUT = 300
REFRESH_URL = "https://accounts.zoho.com/oauth/v2/token"
BASE_API_DOMAIN = "https://www.zohoapis.com"
DEFAULT_EXPIRY_TIME_IN_SECONDS = 3600

def raise_for_error(response: requests.Response) -> None:
    """Raises the associated response exception. Takes in a response object,
    checks the status code, and throws the associated exception based on the
    status code.

    :param resp: requests.Response object
    """
    try:
        response_json = response.json()
    except Exception:
        response_json = {}

    if response.status_code in [200, 201, 204]:
        return

    error_code = response_json.get("code", "").upper()
    error_text = response_json.get("message", "")
    error_status = response_json.get("status", "").lower()
    error_type = response_json.get("error", "").upper()
    error_desc = response_json.get("error_description", "").lower()

    SKIPPABLE_ERRORS = {
        (401, "OAUTH_SCOPE_MISMATCH"): "The OAuth token does not have the required scope to access the stream.",
        (400, "FEATURE_NOT_ENABLED"): "The stream is not available for sync with the current account scope.",
        (400, "NO_PERMISSION"): "The stream is not available for sync; permission denied to access the module.",
    }

    RETRYABLE_ERRORS = {
        (
            400,
            "ACCESS DENIED",
            "too many requests continuously. Please try again after some time."
        ): ZohoCRMRateLimitError
    }

    for (code, err_type, desc_substr), exception_cls in RETRYABLE_ERRORS.items():
        if response.status_code == code and error_type == err_type and desc_substr.lower() in error_desc:
            raise exception_cls(
                f"{code} Retryable Error: {response_json.get('error_description', '')}",
                response
            )

    if (response.status_code, error_code) in SKIPPABLE_ERRORS:
        LOGGER.info(f"Skipping stream: {SKIPPABLE_ERRORS[(response.status_code, error_code)]}")
        return

    if error_status == "error":
        message = (
            f"HTTP-error-code: {response.status_code}, "
            f"Response-error-code: {error_code}, "
            f"Error: {error_text}"
        )
    else:
        default_msg = ERROR_CODE_EXCEPTION_MAPPING.get(
            response.status_code, {}
        ).get("message", "Unknown Error")
        message = f"HTTP-error-code: {response.status_code}, Error: {error_text or default_msg}"

    exception_class = ERROR_CODE_EXCEPTION_MAPPING.get(
        response.status_code, {}
    ).get("raise_exception", ZohoCRMError)

    raise exception_class(message, response) from None


def get_retry_after(exception_info):
    """Returns the retry_after value from RateLimitError exception.
    This is used by backoff.runtime to determine wait time.
    """
    exception = exception_info.get('exception') if isinstance(exception_info, dict) else exception_info

    if exception and isinstance(exception, ZohoCRMRateLimitError):
        retry_after = exception.retry_after if hasattr(exception, 'retry_after') \
                        and exception.retry_after is not None else 60
        LOGGER.info(f"Rate limited. Waiting {retry_after} seconds...")
        return retry_after

    return 60  # Default fallback

class Client:
    """
    A Wrapper class.
    ~~~
    Performs:
     - Authentication
     - Response parsing
     - HTTP Error handling and retry
    """

    def __init__(self, config: Mapping[str, Any], config_path: Optional[str] = None) -> None:
        self.config = config
        self._config_path = config_path
        self._session = session()
        self._scope = None

        # Load persisted token from config if available
        self._access_token = config.get("access_token")
        self._token_type = config.get("token_type", "Bearer")
        self._api_domain = config.get("api_domain", BASE_API_DOMAIN)
        self._expires_at = None
        saved_expiry = config.get("token_expires_at")
        if saved_expiry:
            try:
                # normalise a trailing 'Z' (RFC 3339 / UTC) to '+00:00'
                # because datetime.fromisoformat() does not accept 'Z' on Python < 3.11.
                expiry_str = saved_expiry
                if isinstance(expiry_str, str) and expiry_str.endswith("Z"):
                    expiry_str = expiry_str[:-1] + "+00:00"
                self._expires_at = datetime.fromisoformat(expiry_str)
            except (ValueError, TypeError):
                self._expires_at = None

        self.base_url = f"{self._api_domain}/crm/v8"

        config_request_timeout = config.get("request_timeout")
        self.request_timeout = float(config_request_timeout) if config_request_timeout else REQUEST_TIMEOUT

    def __enter__(self):
        # Reuse saved token if it is still valid; only refresh when missing or expired
        if self._access_token and self._expires_at and self._expires_at > datetime.now(tz=self._expires_at.tzinfo):
            LOGGER.info("Reusing existing access token from config (expires at %s).", self._expires_at)
        else:
            self._refresh_access_token()
        return self

    def __exit__(self, exception_type, exception_value, traceback):
        self._session.close()

    def _refresh_access_token(self) -> None:
        """Refreshes the access token and persists it to the config file."""
        LOGGER.info("Refreshing Access Token")
        resp_json = self.make_request(
            "POST",
            endpoint=REFRESH_URL,
            headers={
                "User-Agent": self.config["user_agent"],
                "Content-Type": "application/json"
            },
            params={
                "refresh_token": self.config["refresh_token"],
                "client_id": self.config["client_id"],
                "client_secret": self.config["client_secret"],
                "grant_type": "refresh_token"
            },
            body={},
            is_auth_req=False
        )
        self._access_token = resp_json.get("access_token")
        self._scope = resp_json.get("scope")
        api_domain = resp_json.get("api_domain")
        if api_domain:
            self._api_domain = api_domain
            self.base_url = f"{self._api_domain}/crm/v8"
        self._token_type = resp_json.get("token_type", "Bearer")
        expires_in_seconds = resp_json.get("expires_in", DEFAULT_EXPIRY_TIME_IN_SECONDS)
        self._expires_at = datetime.now() + timedelta(seconds=expires_in_seconds)
        self._write_config()
        LOGGER.info("Got refreshed access token (expires at %s).", self._expires_at)

    def _write_config(self) -> None:
        """Writes the current access token and expiry back to the config file."""
        if not self._config_path:
            return
        try:
            LOGGER.info("Credentials Refreshed")
            with open(self._config_path) as fh:
                config_data = json.load(fh)
            config_data["access_token"] = self._access_token
            config_data["token_expires_at"] = self._expires_at.isoformat()
            config_data["token_type"] = self._token_type
            if self._api_domain:
                config_data["api_domain"] = self._api_domain
            with open(self._config_path, "w") as fh:
                json.dump(config_data, fh, indent=2)
        except Exception as exc:
            LOGGER.warning("Failed to save access token to config file: %s", exc)

    def get_access_token(self) -> str:
        """Return access token if available or generate one."""
        if self._access_token and self._expires_at and self._expires_at > datetime.now(tz=self._expires_at.tzinfo):
            return self._access_token

        self._refresh_access_token()
        return self._access_token

    @property
    def headers(self) -> Dict[str, str]:
        """
        Construct and return the HTTP headers required for the requests.
        """
        header = {
            'User-Agent': self.config["user_agent"],
            'Content-Type': 'application/json'
        }
        return header

    def authenticate(self, headers: Dict, params: Dict) -> Tuple[Dict, Dict]:
        """Authenticates the request with the token"""
        result_headers = self.headers.copy()
        result_headers["Authorization"] = f"{self._token_type} {self.get_access_token()}"
        if not headers:
            result_headers.pop("Content-Type", None)
        else:
            result_headers.update(headers)
        return result_headers, params

    def make_request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, Any]] = None,
        body: Optional[Dict[str, Any]] = None,
        path: Optional[str] = None,
        is_auth_req: bool = True
    ) -> Any:
        """
        Sends an HTTP request to the specified API endpoint.

        If the token expires mid-sync and the API returns 401, the token is
        refreshed automatically and the request is retried once.
        """
        params = params or {}
        headers = headers or {}
        body = body or {}
        endpoint = endpoint or f"{self.base_url}/{path}"
        if is_auth_req:
            headers, params = self.authenticate(headers, params)
        try:
            return self.__make_request(
                method, endpoint,
                headers=headers,
                params=params,
                data=body,
                timeout=self.request_timeout
            )
        except ZohoCRMUnauthorizedError:
            if not is_auth_req:
                raise
            LOGGER.info("Access token rejected (401). Refreshing token and retrying request.")
            self._refresh_access_token()
            headers, params = self.authenticate(headers, params)
            return self.__make_request(
                method, endpoint,
                headers=headers,
                params=params,
                data=body,
                timeout=self.request_timeout
            )

    @backoff.on_exception(
        wait_gen=backoff.expo,
        exception=(
            ConnectionResetError,
            ConnectionError,
            ChunkedEncodingError,
            Timeout,
            ZohoCRMInternalServerError,
            ZohoCRMServiceUnavailableError
        ),
        max_tries=5,
        factor=2
    )
    @backoff.on_exception(
        backoff.runtime,
        exception=(
            ZohoCRMRateLimitError,
        ),
        max_tries=5,
        value=get_retry_after,
        jitter=None
    )
    def __make_request(
        self, method: str, endpoint: str, **kwargs
    ) -> Optional[Mapping[Any, Any]]:
        """Performs HTTP Operations."""
        method = method.upper()
        with metrics.http_request_timer(endpoint):
            if method in ("GET", "POST"):
                if method == "GET":
                    kwargs.pop("data", None)
                response = self._session.request(method, endpoint, **kwargs)
                raise_for_error(response)
            else:
                raise ValueError(f"Unsupported method: {method}")

        if response.status_code == 204:
            # HTTP 204 No Content: no response body is returned.
            # Return an empty dictionary to maintain consistent response structure.
            return {}

        return response.json()

