from typing import Any, Dict, Mapping, Optional, Tuple
from datetime import datetime, timedelta
import time

import backoff
import requests
from requests import session
from requests.exceptions import Timeout, ConnectionError, ChunkedEncodingError
from singer import get_logger, metrics

from tap_zoho_crm.exceptions import (
    ERROR_CODE_EXCEPTION_MAPPING,
    ZohoCRMError,
    ZohoCRMRateLimitError,
    ZohoCRMInternalServerError,
    ZohoCRMServiceUnavailableError
    )

LOGGER = get_logger()
REQUEST_TIMEOUT = 300
REFRESH_URL = "https://accounts.zoho.com/oauth/v2/token"
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


def wait_if_retry_after(details):
    """Backoff handler that checks for a 'retry_after' attribute in the exception
    and sleeps for the specified duration to respect API rate limits.
    """
    exc = details['exception']
    if hasattr(exc, 'retry_after') and exc.retry_after is not None:
        LOGGER.warning(f"Rate limited. Retrying in {exc.retry_after} seconds...")
        time.sleep(exc.retry_after)

class Client:
    """
    A Wrapper class.
    ~~~
    Performs:
     - Authentication
     - Response parsing
     - HTTP Error handling and retry
    """

    def __init__(self, config: Mapping[str, Any]) -> None:
        self.config = config
        self._session = session()
        self._access_token = None
        self._expires_at = None
        self._scope = None
        self._api_domain = "https://www.zohoapis.com"
        self._token_type = None
        self.base_url = f"{self._api_domain}/crm/{self.config.get('api_version', 'v8')}"

        config_request_timeout = config.get("request_timeout")
        self.request_timeout = float(config_request_timeout) if config_request_timeout else REQUEST_TIMEOUT

    def __enter__(self):
        self._refresh_access_token()
        return self

    def __exit__(self, exception_type, exception_value, traceback):
        self._session.close()

    def _refresh_access_token(self) -> None:
        """Refreshes the access token."""
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
        self._api_domain = resp_json.get("api_domain")
        self._token_type = resp_json.get("token_type", "Bearer")
        expires_in_seconds = resp_json.get("expires_in", DEFAULT_EXPIRY_TIME_IN_SECONDS)
        self._expires_at = datetime.now() + timedelta(seconds=expires_in_seconds)
        LOGGER.info("Got refreshed access token")

    def get_access_token(self) -> str:
        """Return access token if available or generate one."""
        if self._access_token and self._expires_at > datetime.now():
            return self._access_token

        self._refresh_access_token()
        return self._access_token

    @property
    def headers(self) -> Dict[str, str]:
        """
        Construct and return the HTTP headers required for requests to the Amazon Advertising API.
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
        """
        params = params or {}
        headers = headers or {}
        body = body or {}
        endpoint = endpoint or f"{self.base_url}/{path}"
        if is_auth_req:
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
        wait_gen=backoff.constant,
        on_backoff=wait_if_retry_after,
        exception=(
            ZohoCRMRateLimitError,
        ),
        max_tries=3,
        interval=1
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

