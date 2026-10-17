"""Version helpers for the XRTM meta-package."""

from importlib.metadata import PackageNotFoundError, version

# Keep in sync with pyproject.toml (a test enforces this source literal).
_FALLBACK_VERSION = "0.10.7"

try:
    __version__ = version("xrtm")
except PackageNotFoundError:  # pragma: no cover - editable source tree fallback
    __version__ = _FALLBACK_VERSION

__all__ = ["__version__"]
