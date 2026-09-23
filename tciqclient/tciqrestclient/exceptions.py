"""Exception types raised by the tciqrestclient package."""


class IQError(Exception):
    """Base class for all tciqrestclient errors."""


class IQConfigError(IQError):
    """Raised when connection configuration cannot be resolved from
    explicit arguments, environment variables, or a .env file."""


class IQConnectionError(IQError):
    """Raised when the orion-res address cannot be discovered."""


class IQRequestError(IQError):
    """Raised when an HTTP request to orion-res fails or returns an
    error status."""


class IQQueryError(IQError):
    """Raised for query composition or execution failures."""


class IQViewError(IQError):
    """Raised for named-view failures."""


class IQReportError(IQError):
    """Raised for report generation/download failures."""
