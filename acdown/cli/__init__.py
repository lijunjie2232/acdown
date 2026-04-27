"""CLI module for ACDown Client."""

from acdown.cli.cli import app
from acdown.auth import AuthManager
from acdown.downloader import Downloader

__all__ = ["app", "AuthManager", "Downloader"]
