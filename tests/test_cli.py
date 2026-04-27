"""Tests for CLI interface."""

import pytest
from typer.testing import CliRunner
from unittest.mock import patch, MagicMock, AsyncMock
import asyncio

from acdown.cli import app


runner = CliRunner()


class TestDownloadCommand:
    """Test the download command."""

    @patch('acdown.cli.AuthManager')
    @patch('acdown.cli.Downloader')
    def test_download_success(self, mock_downloader_class, mock_auth_class):
        """Test successful download."""
        # Setup mocks
        mock_auth = MagicMock()
        mock_auth.is_server_url_configured.return_value = True
        mock_auth.is_token_valid.return_value = True
        mock_auth.get_token.return_value = 'test_token'
        mock_auth.get_config.return_value = {
            'server_url': 'http://test-server:8787',
            'parallel': 3,
            'verbose': False,
            'output': '.'
        }
        mock_auth_class.return_value = mock_auth
        
        # Mock downloader
        mock_downloader = AsyncMock()
        from pathlib import Path
        output_file = Path('/tmp/test.zip')
        output_file.write_bytes(b'test data')
        
        async def mock_download(*args, **kwargs):
            return output_file
        
        mock_downloader.download = mock_download
        mock_downloader_class.return_value = mock_downloader
        
        result = runner.invoke(app, ['download', 'https://example.com/file.zip'])
        
        assert result.exit_code == 0
        assert "Download complete" in result.stdout

    @patch('acdown.cli.AuthManager')
    def test_download_no_server_url(self, mock_auth_class):
        """Test download when server URL not configured."""
        mock_auth = MagicMock()
        mock_auth.is_server_url_configured.return_value = False
        mock_auth_class.return_value = mock_auth
        
        result = runner.invoke(app, ['download', 'https://example.com/file.zip'])
        
        assert result.exit_code == 1
        assert "Server URL not configured" in result.stdout

    @patch('acdown.cli.AuthManager')
    def test_download_invalid_url(self, mock_auth_class):
        """Test download with invalid URL."""
        mock_auth = MagicMock()
        mock_auth.is_server_url_configured.return_value = True
        mock_auth_class.return_value = mock_auth
        
        result = runner.invoke(app, ['download', 'not-a-valid-url'])
        
        assert result.exit_code == 1
        assert "Invalid URL" in result.stdout

    @patch('acdown.cli.AuthManager')
    def test_download_not_authenticated(self, mock_auth_class):
        """Test download without authentication."""
        mock_auth = MagicMock()
        mock_auth.is_server_url_configured.return_value = True
        mock_auth.is_token_valid.return_value = False
        mock_auth_class.return_value = mock_auth
        
        result = runner.invoke(app, ['download', 'https://example.com/file.zip'])
        
        assert result.exit_code == 1
        assert "Not authenticated" in result.stdout

    @patch('acdown.cli.AuthManager')
    @patch('acdown.cli.Downloader')
    def test_download_with_options(self, mock_downloader_class, mock_auth_class):
        """Test download with custom options."""
        mock_auth = MagicMock()
        mock_auth.is_server_url_configured.return_value = True
        mock_auth.is_token_valid.return_value = True
        mock_auth.get_token.return_value = 'test_token'
        mock_auth.get_config.return_value = {
            'server_url': 'http://test-server:3000',
            'parallel': 3,
            'verbose': False,
            'output': '.'
        }
        mock_auth_class.return_value = mock_auth
        
        mock_downloader = AsyncMock()
        from pathlib import Path
        output_file = Path('/tmp/custom.zip')
        output_file.write_bytes(b'test data')
        
        async def mock_download(*args, **kwargs):
            return output_file
        
        mock_downloader.download = mock_download
        mock_downloader_class.return_value = mock_downloader
        
        result = runner.invoke(app, [
            'download',
            'https://example.com/file.zip',
            '-o', '/tmp/custom.zip',
            '-c', '5',
            '-v'
        ])
        
        assert result.exit_code == 0
        
        # Verify config was updated with command-line options
        call_args = mock_downloader_class.call_args
        config = call_args[0][0]
        assert config['parallel'] == 5
        assert config['verbose'] is True


class TestAuthCommand:
    """Test the auth command."""

    @patch('acdown.cli.AuthManager')
    def test_auth_success(self, mock_auth_class):
        """Test successful authentication."""
        mock_auth = MagicMock()
        mock_auth.is_server_url_configured.return_value = True
        
        async def mock_login(code):
            return {'token': 'new_token', 'expiresAt': 9999999999999}
        
        mock_auth.login = mock_login
        mock_auth.get_config.return_value = {'server_url': 'http://test-server:3000'}
        mock_auth_class.return_value = mock_auth
        
        result = runner.invoke(app, ['auth', '123456'])
        
        assert result.exit_code == 0
        assert "Authentication successful" in result.stdout

    @patch('acdown.cli.AuthManager')
    def test_auth_no_server_url(self, mock_auth_class):
        """Test auth when server URL not configured."""
        mock_auth = MagicMock()
        mock_auth.is_server_url_configured.return_value = False
        mock_auth_class.return_value = mock_auth
        
        result = runner.invoke(app, ['auth', '123456'])
        
        assert result.exit_code == 1
        assert "Server URL not configured" in result.stdout

    @patch('acdown.cli.AuthManager')
    def test_auth_failure(self, mock_auth_class):
        """Test authentication failure."""
        mock_auth = MagicMock()
        mock_auth.is_server_url_configured.return_value = True
        
        async def mock_login(code):
            raise Exception("Invalid TOTP code")
        
        mock_auth.login = mock_login
        mock_auth_class.return_value = mock_auth
        
        result = runner.invoke(app, ['auth', 'invalid'])
        
        assert result.exit_code == 1
        assert "Authentication failed" in result.stdout


class TestConfigCommand:
    """Test the config command."""

    @patch('acdown.cli.AuthManager')
    def test_config_set_success(self, mock_auth_class):
        """Test setting configuration."""
        mock_auth = MagicMock()
        mock_auth_class.return_value = mock_auth
        
        result = runner.invoke(app, ['config', 'set', 'server_url', 'http://example.com:3000'])
        
        assert result.exit_code == 0
        assert "Configuration updated" in result.stdout
        mock_auth.set_config.assert_called_once_with('server_url', 'http://example.com:3000')

    @patch('acdown.cli.AuthManager')
    def test_config_set_missing_args(self, mock_auth_class):
        """Test config set with missing arguments."""
        mock_auth = MagicMock()
        mock_auth_class.return_value = mock_auth
        
        result = runner.invoke(app, ['config', 'set'])
        
        assert result.exit_code == 1
        assert "Usage:" in result.stdout

    @patch('acdown.cli.AuthManager')
    def test_config_set_invalid_key(self, mock_auth_class):
        """Test config set with invalid key."""
        mock_auth = MagicMock()
        mock_auth_class.return_value = mock_auth
        
        result = runner.invoke(app, ['config', 'set', 'invalid_key', 'value'])
        
        assert result.exit_code == 1
        assert "Invalid key" in result.stdout

    @patch('acdown.cli.AuthManager')
    def test_config_get_all(self, mock_auth_class):
        """Test getting all configuration."""
        mock_auth = MagicMock()
        mock_auth.get_config.return_value = {
            'server_url': 'http://test-server:3000',
            'parallel': 5,
            'verbose': True,
            'output': '/tmp/downloads'
        }
        mock_auth_class.return_value = mock_auth
        
        result = runner.invoke(app, ['config', 'get'])
        
        assert result.exit_code == 0
        assert "Current Configuration" in result.stdout
        assert "server_url" in result.stdout
        assert "parallel" in result.stdout

    @patch('acdown.cli.AuthManager')
    def test_config_get_specific_key(self, mock_auth_class):
        """Test getting specific configuration value."""
        mock_auth = MagicMock()
        mock_auth.get_config_value.return_value = 'http://test-server:3000'
        mock_auth_class.return_value = mock_auth
        
        result = runner.invoke(app, ['config', 'get', 'server_url'])
        
        assert result.exit_code == 0
        assert "server_url" in result.stdout
        assert "http://test-server:3000" in result.stdout

    @patch('acdown.cli.AuthManager')
    def test_config_invalid_action(self, mock_auth_class):
        """Test config with invalid action."""
        mock_auth = MagicMock()
        mock_auth_class.return_value = mock_auth
        
        result = runner.invoke(app, ['config', 'invalid'])
        
        assert result.exit_code == 1
        assert "Invalid action" in result.stdout


class TestLogoutCommand:
    """Test the logout command."""

    @patch('acdown.cli.AuthManager')
    def test_logout_success(self, mock_auth_class):
        """Test successful logout."""
        mock_auth = MagicMock()
        mock_auth_class.return_value = mock_auth
        
        result = runner.invoke(app, ['logout'])
        
        assert result.exit_code == 0
        assert "Logged out successfully" in result.stdout
        mock_auth.logout.assert_called_once()

    @patch('acdown.cli.AuthManager')
    def test_logout_failure(self, mock_auth_class):
        """Test logout failure."""
        mock_auth = MagicMock()
        mock_auth.logout.side_effect = Exception("Error")
        mock_auth_class.return_value = mock_auth
        
        result = runner.invoke(app, ['logout'])
        
        assert result.exit_code == 1
        assert "Logout failed" in result.stdout


class TestHelpAndUsage:
    """Test help messages and usage information."""

    def test_main_help(self):
        """Test main help message."""
        result = runner.invoke(app, ['--help'])
        
        assert result.exit_code == 0
        assert "acdown" in result.stdout.lower()
        assert "download" in result.stdout.lower()

    def test_download_help(self):
        """Test download command help."""
        result = runner.invoke(app, ['download', '--help'])
        
        assert result.exit_code == 0
        assert "URL to download" in result.stdout

    def test_auth_help(self):
        """Test auth command help."""
        result = runner.invoke(app, ['auth', '--help'])
        
        assert result.exit_code == 0
        assert "TOTP" in result.stdout

    def test_config_help(self):
        """Test config command help."""
        result = runner.invoke(app, ['config', '--help'])
        
        assert result.exit_code == 0
        assert "Manage server configuration" in result.stdout

    def test_logout_help(self):
        """Test logout command help."""
        result = runner.invoke(app, ['logout', '--help'])
        
        assert result.exit_code == 0
        assert "Clear saved authentication token" in result.stdout


class TestEdgeCases:
    """Test edge cases and error handling."""

    @patch('acdown.cli.AuthManager')
    @patch('acdown.cli.Downloader')
    def test_download_exception_handling(self, mock_downloader_class, mock_auth_class):
        """Test download with exception during download."""
        mock_auth = MagicMock()
        mock_auth.is_server_url_configured.return_value = True
        mock_auth.is_token_valid.return_value = True
        mock_auth.get_token.return_value = 'test_token'
        mock_auth.get_config.return_value = {
            'server_url': 'http://test-server:3000',
            'parallel': 3,
            'verbose': False,
            'output': '.'
        }
        mock_auth_class.return_value = mock_auth
        
        mock_downloader = AsyncMock()
        
        async def mock_download_error(*args, **kwargs):
            raise Exception("Network error")
        
        mock_downloader.download = mock_download_error
        mock_downloader_class.return_value = mock_downloader
        
        result = runner.invoke(app, ['download', 'https://example.com/file.zip'])
        
        assert result.exit_code == 1
        assert "Download failed" in result.stdout
        assert "Network error" in result.stdout

    @patch('acdown.cli.AuthManager')
    def test_config_set_exception_handling(self, mock_auth_class):
        """Test config set with exception."""
        mock_auth = MagicMock()
        mock_auth.set_config.side_effect = Exception("Permission denied")
        mock_auth_class.return_value = mock_auth
        
        result = runner.invoke(app, ['config', 'set', 'server_url', 'http://example.com'])
        
        assert result.exit_code == 1
        assert "Failed to set config" in result.stdout
