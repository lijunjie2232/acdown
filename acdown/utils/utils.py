"""Utility functions for ACDown client."""

import os
import sys
import shutil
from pathlib import Path
from urllib.parse import urlparse, unquote
from typing import Optional


def extract_filename_from_url(url: str) -> str:
    """Extract filename from URL.
    
    Args:
        url: The download URL
        
    Returns:
        Filename extracted from URL or 'download.bin' as fallback
    """
    parsed = urlparse(url)
    path = unquote(parsed.path)
    filename = os.path.basename(path)
    
    if not filename or filename == '':
        return 'download.bin'
    
    return filename


def validate_url(url: str) -> bool:
    """Validate if the given string is a valid URL.
    
    Args:
        url: URL string to validate
        
    Returns:
        True if URL appears valid, False otherwise
    """
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except:
        return False


def check_disk_space(output_path: Path, required_bytes: int) -> bool:
    """Check if there's enough disk space for the download.
    
    Args:
        output_path: Path where file will be saved
        required_bytes: Required disk space in bytes
        
    Returns:
        True if sufficient space available, False otherwise
    """
    try:
        # Get the directory where file will be saved
        output_dir = output_path.parent if output_path.parent != Path('.') else Path.cwd()
        usage = shutil.disk_usage(output_dir)
        return usage.free >= required_bytes
    except:
        # If we can't check, assume it's OK
        return True


def format_size(size_bytes: int) -> str:
    """Format byte size to human-readable string.
    
    Args:
        size_bytes: Size in bytes
        
    Returns:
        Formatted string (e.g., "128.00 MB")
    """
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.2f} PB"


def format_duration(seconds: float) -> str:
    """Format duration in seconds to human-readable string.
    
    Args:
        seconds: Duration in seconds
        
    Returns:
        Formatted string (e.g., "2m 30s" or "45.5s")
    """
    if seconds < 60:
        return f"{seconds:.1f}s"
    elif seconds < 3600:
        minutes = int(seconds // 60)
        secs = seconds % 60
        return f"{minutes}m {secs:.0f}s"
    else:
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        return f"{hours}h {minutes}m"


def get_app_data_dir(app_name: str = "acdown") -> Path:
    """Get the application data directory for storing config and tokens.
    
    Cross-platform support:
    - Linux: ~/.local/share/<app_name>
    - macOS: ~/Library/Application Support/<app_name>
    - Windows: C:\\Users\\<user>\\AppData\\Local\\<app_name>
    
    Args:
        app_name: Application name for directory
        
    Returns:
        Path to the application data directory
    """
    system = sys.platform
    
    if system == "win32":
        # Windows: C:\Users\<user>\AppData\Local\<app_name>
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    elif system == "darwin":
        # macOS: ~/Library/Application Support/<app_name>
        base = Path.home() / "Library" / "Application Support"
    else:
        # Linux and others: ~/.local/share/<app_name>
        base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    
    app_dir = base / app_name
    app_dir.mkdir(parents=True, exist_ok=True)
    
    return app_dir
