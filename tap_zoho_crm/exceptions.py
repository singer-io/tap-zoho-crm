class ZohoCRMError(Exception):
    """class representing Generic Http error."""

    def __init__(self, message=None, response=None):
        super().__init__(message)
        self.message = message
        self.response = response


class ZohoCRMBackoffError(ZohoCRMError):
    """class representing backoff error handling."""
    pass

class ZohoCRMBadRequestError(ZohoCRMError):
    """class representing 400 status code."""
    pass

class ZohoCRMUnauthorizedError(ZohoCRMError):
    """class representing 401 status code."""
    pass


class ZohoCRMForbiddenError(ZohoCRMError):
    """class representing 403 status code."""
    pass

class ZohoCRMNotFoundError(ZohoCRMError):
    """class representing 404 status code."""
    pass

class ZohoCRMConflictError(ZohoCRMError):
    """class representing 406 status code."""
    pass

class ZohoCRMUnprocessableEntityError(ZohoCRMBackoffError):
    """class representing 409 status code."""
    pass

class ZohoCRMRateLimitError(ZohoCRMBackoffError):
    """class representing 429 status code."""
    def __init__(self, message=None, response=None):
        """Initialize the ZohoCRMRateLimitError. Parses the 'retry_in_seconds'  from the response (if present) and sets the
            `retry_after` attribute accordingly.
        """
        self.response = response
        self.retry_after = None

        if response is not None:
            try:
                self.retry_after = int(response.headers.get("Retry-After", 60))
            except (ValueError, TypeError):
                self.retry_after = 60
        base_msg = message or "Rate limit exhausted"
        retry_info = f"(Retry after {self.retry_after} seconds.)" \
            if self.retry_after is not None else "(Retry after unknown delay.)"
        full_message = f"{base_msg} {retry_info}"
        super().__init__(full_message, response=response)

class ZohoCRMInternalServerError(ZohoCRMBackoffError):
    """class representing 500 status code."""
    pass

class ZohoCRMNotImplementedError(ZohoCRMBackoffError):
    """class representing 501 status code."""
    pass

class ZohoCRMBadGatewayError(ZohoCRMBackoffError):
    """class representing 502 status code."""
    pass

class ZohoCRMServiceUnavailableError(ZohoCRMBackoffError):
    """class representing 503 status code."""
    pass

ERROR_CODE_EXCEPTION_MAPPING = {
    400: {
        "raise_exception": ZohoCRMBadRequestError,
        "message": "A validation exception has occurred."
    },
    401: {
        "raise_exception": ZohoCRMUnauthorizedError,
        "message": "The access token provided is expired, revoked, malformed or invalid for other reasons."
    },
    403: {
        "raise_exception": ZohoCRMForbiddenError,
        "message": "You are missing the following required scopes: read"
    },
    404: {
        "raise_exception": ZohoCRMNotFoundError,
        "message": "The resource you have specified cannot be found."
    },
    409: {
        "raise_exception": ZohoCRMConflictError,
        "message": "The API request cannot be completed because the requested operation would conflict with an existing item."
    },
    422: {
        "raise_exception": ZohoCRMUnprocessableEntityError,
        "message": "The request content itself is not processable by the server."
    },
    429: {
        "raise_exception": ZohoCRMRateLimitError,
        "message": "The API rate limit for your organisation/application pairing has been exceeded."
    },
    500: {
        "raise_exception": ZohoCRMInternalServerError,
        "message": "The server encountered an unexpected condition which prevented" \
            " it from fulfilling the request."
    },
    501: {
        "raise_exception": ZohoCRMNotImplementedError,
        "message": "The server does not support the functionality required to fulfill the request."
    },
    502: {
        "raise_exception": ZohoCRMBadGatewayError,
        "message": "Server received an invalid response."
    },
    503: {
        "raise_exception": ZohoCRMServiceUnavailableError,
        "message": "API service is currently unavailable."
    }
}

