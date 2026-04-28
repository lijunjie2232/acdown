"""ACDown Client - A command-line download client for ACDown Server."""

__version__ = "0.2.0"
__author__ = "ACDown Team"

from acdown.auth import AuthManager
from acdown.downloader import Downloader
from acdown.progress import ProgressTracker
from acdown.utils import (
    extract_filename_from_url,
    validate_url,
    check_disk_space,
    format_size,
    format_duration,
    get_app_data_dir,
    setup_logging,
    get_logger,
)

__all__ = [
    "AuthManager",
    "Downloader",
    "ProgressTracker",
    "extract_filename_from_url",
    "validate_url",
    "check_disk_space",
    "format_size",
    "format_duration",
    "get_app_data_dir",
    "setup_logging",
    "get_logger",
]
