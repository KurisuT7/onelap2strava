class Onelap2StravaError(Exception):
    """Base exception for expected application errors."""


class FitError(Onelap2StravaError):
    """Raised when a FIT file cannot be safely converted."""


class ConfigError(Onelap2StravaError):
    """Raised when local configuration is missing or invalid."""


class ServiceError(Onelap2StravaError):
    """Raised when an external service request fails."""
