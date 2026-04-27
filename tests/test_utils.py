"""Tests for utility functions."""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
import os
import sys
import tempfile
import shutil

from acdown.utils import (
    extract_filename_from_url,
    validate_url,
    check_disk_space,
    format_size,
    format_duration,
    get_app_data_dir,
)


class TestExtractFilenameFromURL:
    """Test URL filename extraction."""

    def test_extract_simple_filename(self):
        """Test extracting filename from simple URL."""
        url = "https://example.com/file.zip"
        assert extract_filename_from_url(url) == "file.zip"

    def test_extract_filename_with_path(self):
        """Test extracting filename from URL with path."""
        url = "https://example.com/path/to/file.tar.gz"
        assert extract_filename_from_url(url) == "file.tar.gz"

    def test_extract_filename_with_query_params(self):
        """Test extracting filename from URL with query parameters."""
        url = "https://example.com/download?file=archive.zip&version=1.0"
        # Should return 'download' as there's no actual filename in path
        result = extract_filename_from_url(url)
        assert result in ['download', 'download.bin']

    def test_extract_filename_encoded(self):
        """Test extracting filename with URL encoding."""
        url = "https://example.com/my%20file.zip"
        assert extract_filename_from_url(url) == "my file.zip"

    def test_extract_filename_no_extension(self):
        """Test extracting filename without extension."""
        url = "https://example.com/README"
        assert extract_filename_from_url(url) == "README"

    def test_extract_filename_root_url(self):
        """Test extracting filename from root URL."""
        url = "https://example.com/"
        assert extract_filename_from_url(url) == "download.bin"

    def test_extract_filename_empty_path(self):
        """Test extracting filename from URL with empty path."""
        url = "https://example.com"
        assert extract_filename_from_url(url) == "download.bin"

    def test_extract_filename_complex_url(self):
        """Test extracting filename from complex URL."""
        url = "https://cdn.example.com/releases/v1.0.0/app-x64-linux.deb"
        assert extract_filename_from_url(url) == "app-x64-linux.deb"


class TestValidateURL:
    """Test URL validation."""

    def test_valid_http_url(self):
        """Test validation of HTTP URL."""
        assert validate_url("http://example.com") is True

    def test_valid_https_url(self):
        """Test validation of HTTPS URL."""
        assert validate_url("https://example.com/file.zip") is True

    def test_valid_url_with_port(self):
        """Test validation of URL with port."""
        assert validate_url("http://localhost:3000") is True

    def test_valid_url_with_path(self):
        """Test validation of URL with path."""
        assert validate_url("https://example.com/path/to/resource") is True

    def test_invalid_no_scheme(self):
        """Test validation of URL without scheme."""
        assert validate_url("example.com") is False

    def test_invalid_no_domain(self):
        """Test validation of URL without domain."""
        assert validate_url("http://") is False

    def test_invalid_empty_string(self):
        """Test validation of empty string."""
        assert validate_url("") is False

    def test_invalid_just_text(self):
        """Test validation of plain text."""
        assert validate_url("not a url") is False

    def test_valid_ftp_url(self):
        """Test validation of FTP URL."""
        assert validate_url("ftp://ftp.example.com/file.txt") is True

    def test_valid_url_with_subdomain(self):
        """Test validation of URL with subdomain."""
        assert validate_url("https://cdn.example.com") is True


class TestCheckDiskSpace:
    """Test disk space checking."""

    def test_sufficient_disk_space(self, temp_dir):
        """Test when sufficient disk space is available."""
        output_path = temp_dir / "file.bin"
        required_bytes = 1024  # 1 KB
        
        # Mock disk usage to show plenty of space
        with patch('shutil.disk_usage') as mock_usage:
            mock_usage.return_value = MagicMock(total=1000000, used=500000, free=500000)
            
            assert check_disk_space(output_path, required_bytes) is True

    def test_insufficient_disk_space(self, temp_dir):
        """Test when insufficient disk space is available."""
        output_path = temp_dir / "file.bin"
        required_bytes = 1000000  # 1 MB
        
        # Mock disk usage to show very little space
        with patch('shutil.disk_usage') as mock_usage:
            mock_usage.return_value = MagicMock(total=1000000, used=999000, free=1000)
            
            assert check_disk_space(output_path, required_bytes) is False

    def test_check_disk_space_on_error(self, temp_dir):
        """Test disk space check handles errors gracefully."""
        output_path = temp_dir / "file.bin"
        
        # Mock disk_usage to raise exception
        with patch('shutil.disk_usage', side_effect=Exception("Error")):
            # Should return True (assume OK) on error
            assert check_disk_space(output_path, 1024) is True

    def test_check_disk_space_current_directory(self):
        """Test disk space check for current directory."""
        output_path = Path("file.bin")  # Relative path
        
        with patch('shutil.disk_usage') as mock_usage:
            mock_usage.return_value = MagicMock(total=1000000, used=500000, free=500000)
            
            assert check_disk_space(output_path, 1024) is True


class TestFormatSize:
    """Test file size formatting."""

    def test_format_zero_bytes(self):
        """Test formatting zero bytes."""
        assert format_size(0) == "0.00 B"

    def test_format_bytes(self):
        """Test formatting byte values."""
        assert format_size(100) == "100.00 B"
        assert format_size(1023) == "1023.00 B"

    def test_format_kilobytes(self):
        """Test formatting kilobyte values."""
        assert format_size(1024) == "1.00 KB"
        assert format_size(2048) == "2.00 KB"
        assert format_size(5120) == "5.00 KB"
        assert format_size(10240) == "10.00 KB"

    def test_format_megabytes(self):
        """Test formatting megabyte values."""
        assert format_size(1048576) == "1.00 MB"  # 1 MB
        assert format_size(5242880) == "5.00 MB"  # 5 MB
        assert format_size(10485760) == "10.00 MB"  # 10 MB

    def test_format_gigabytes(self):
        """Test formatting gigabyte values."""
        assert format_size(1073741824) == "1.00 GB"  # 1 GB
        assert format_size(5368709120) == "5.00 GB"  # 5 GB

    def test_format_terabytes(self):
        """Test formatting terabyte values."""
        assert format_size(1099511627776) == "1.00 TB"  # 1 TB

    def test_format_petabytes(self):
        """Test formatting petabyte values."""
        pb = 1125899906842624  # 1 PB
        result = format_size(pb)
        assert "PB" in result


class TestFormatDuration:
    """Test duration formatting."""

    def test_format_seconds_less_than_60(self):
        """Test formatting durations less than 60 seconds."""
        assert format_duration(0) == "0.0s"
        assert format_duration(1.5) == "1.5s"
        assert format_duration(30.7) == "30.7s"
        assert format_duration(59.9) == "59.9s"

    def test_format_minutes(self):
        """Test formatting durations in minutes."""
        assert format_duration(60) == "1m 0s"
        assert format_duration(90) == "1m 30s"
        assert format_duration(120) == "2m 0s"
        assert format_duration(359) == "5m 59s"

    def test_format_hours(self):
        """Test formatting durations in hours."""
        assert format_duration(3600) == "1h 0m"
        assert format_duration(5400) == "1h 30m"  # 1.5 hours
        assert format_duration(7200) == "2h 0m"
        assert format_duration(3661) == "1h 1m"  # 1 hour 1 minute 1 second

    def test_format_large_durations(self):
        """Test formatting very large durations."""
        assert format_duration(86400) == "24h 0m"  # 1 day
        assert format_duration(90061) == "25h 1m"  # 25 hours 1 minute 1 second


class TestGetAppDataDir:
    """Test application data directory detection."""

    def test_get_app_data_dir_linux(self):
        """Test app data directory on Linux."""
        with patch('sys.platform', 'linux'):
            with patch.dict(os.environ, {}, clear=False):
                dir_path = get_app_data_dir("testapp")
                
                expected = Path.home() / ".local" / "share" / "testapp"
                assert dir_path == expected
                assert dir_path.exists()

    def test_get_app_data_dir_macos(self):
        """Test app data directory on macOS."""
        with patch('sys.platform', 'darwin'):
            dir_path = get_app_data_dir("testapp")
            
            expected = Path.home() / "Library" / "Application Support" / "testapp"
            assert dir_path == expected
            assert dir_path.exists()

    def test_get_app_data_dir_windows(self):
        """Test app data directory on Windows."""
        with patch('sys.platform', 'win32'):
            with patch.dict(os.environ, {'LOCALAPPDATA': str(Path.home() / "AppData" / "Local")}):
                dir_path = get_app_data_dir("testapp")
                
                expected = Path.home() / "AppData" / "Local" / "testapp"
                assert dir_path == expected
                assert dir_path.exists()

    def test_get_app_data_dir_custom_name(self):
        """Test app data directory with custom application name."""
        with patch('sys.platform', 'linux'):
            dir_path = get_app_data_dir("my-custom-app")
            
            expected = Path.home() / ".local" / "share" / "my-custom-app"
            assert dir_path == expected

    def test_get_app_data_dir_creates_directory(self):
        """Test that app data directory is created if it doesn't exist."""
        temp_base = Path(tempfile.mkdtemp())
        
        try:
            with patch('sys.platform', 'linux'):
                with patch.dict(os.environ, {'XDG_DATA_HOME': str(temp_base)}):
                    dir_path = get_app_data_dir("newapp")
                    
                    assert dir_path.exists()
                    assert dir_path.is_dir()
        finally:
            shutil.rmtree(temp_base)

    def test_get_app_data_dir_default_name(self):
        """Test app data directory with default name."""
        with patch('sys.platform', 'linux'):
            dir_path = get_app_data_dir()
            
            expected = Path.home() / ".local" / "share" / "acdown"
            assert dir_path == expected

    def test_get_app_data_dir_xdg_data_home(self):
        """Test app data directory respects XDG_DATA_HOME on Linux."""
        custom_xdg = Path(tempfile.mkdtemp())
        
        try:
            with patch('sys.platform', 'linux'):
                with patch.dict(os.environ, {'XDG_DATA_HOME': str(custom_xdg)}):
                    dir_path = get_app_data_dir("testapp")
                    
                    expected = custom_xdg / "testapp"
                    assert dir_path == expected
        finally:
            shutil.rmtree(custom_xdg)


class TestIntegration:
    """Integration tests for utility functions."""

    def test_url_validation_and_extraction(self):
        """Test URL validation followed by filename extraction."""
        valid_urls = [
            ("https://example.com/file.zip", "file.zip"),
            ("http://cdn.example.com/path/archive.tar.gz", "archive.tar.gz"),
            ("https://releases.github.com/app-v1.0.exe", "app-v1.0.exe"),
        ]
        
        for url, expected_filename in valid_urls:
            assert validate_url(url) is True
            assert extract_filename_from_url(url) == expected_filename

    def test_size_and_duration_formatting(self):
        """Test combined size and duration formatting."""
        # Typical download scenario
        file_size = 104857600  # 100 MB
        download_time = 125.5  # ~2 minutes
        
        size_str = format_size(file_size)
        duration_str = format_duration(download_time)
        
        assert size_str == "100.00 MB"
        assert duration_str == "2m 6s"
