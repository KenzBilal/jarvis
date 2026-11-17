"""JARVIS - AI crypto research & trading platform."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("jarvis-backend")
except PackageNotFoundError:  # pragma: no cover - only when running from an uninstalled checkout
    __version__ = "0.0.0+unknown"

__all__ = ["__version__"]
