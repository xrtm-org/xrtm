"""Top-level product shell for XRTM."""

from pkgutil import extend_path

from xrtm.version import __version__

__path__ = extend_path(__path__, __name__)

__all__ = ["__version__"]
