"""Version helpers for the XRTM meta-package."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("xrtm")
except PackageNotFoundError:  # pragma: no cover - editable source tree fallback
    __version__ = "0.7.1"

__all__ = ["__version__"]
