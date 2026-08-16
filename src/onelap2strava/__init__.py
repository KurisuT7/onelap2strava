from importlib.metadata import PackageNotFoundError, version

from .fit import ConversionResult, convert_fit_bytes, convert_fit_file
from .geo import gcj02_to_wgs84, wgs84_to_gcj02

try:
    __version__ = version("onelap2strava")
except PackageNotFoundError:  # pragma: no cover - source tree without installation
    __version__ = "0.0.0"

__all__ = [
    "ConversionResult",
    "__version__",
    "convert_fit_bytes",
    "convert_fit_file",
    "gcj02_to_wgs84",
    "wgs84_to_gcj02",
]
