"""Tests for authentication and configuration management."""

import pytest
import json
import struct
import time
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock
import asyncio

from acdown.auth import AuthManager


class TestAuthManagerInit:
    """Test AuthManager initialization."""

    def test_init_creates_app_dir(self, temp_dir):
        """Test that AuthManager initializes with correct directory."""
        with patch('acdown.auth.get_app_data_dir', return_value=temp_dir):
            auth = AuthManager()
            assert auth.app_dir == temp_dir
            assert auth.data_file == temp_dir / 'data.bin'

    def test_default_config_values(self, temp_dir):
        """Test default configuration values."""
        with patch('acdown.auth.get_app_data_dir', return_value=temp_dir):
            auth = AuthManager()
            assert auth.default_config['server_url'] == ''
            assert auth.default_config['parallel'] == 3
            assert auth.default_config['verbose'] is False
            assert auth.default_config['output'] == '.'


class TestBinarySerialization:
    """Test binary data encryption/decryption."""

    def test_encrypt_decrypt_roundtrip(self, temp_dir, mock_auth_data):
        """Test that encrypt and decrypt are inverse operations."""
        with patch('acdown.auth.get_app_data_dir', return_value=temp_dir):
            auth = AuthManager()
            
            config = mock_auth_data['config']
            token = mock_auth_data['token']
            expires_at = mock_auth_data['expiresAt']
            
            # Encrypt
            encrypted = auth._encrypt_data(config, token, expires_at)
            
            # Decrypt
            decrypted = auth._decrypt_data(encrypted)
            
            assert decrypted['config'] == config
            assert decrypted['token'] == token
            assert decrypted['expiresAt'] == expires_at

    def test_encrypt_data_format(self, temp_dir):
        """Test binary format structure."""
        with patch('acdown.auth.get_app_data_dir', return_value=temp_dir):
            auth = AuthManager()
            
            config = {'test': 'value'}
            token = 'test_token'
            expires_at = 1234567890
            
            encrypted = auth._encrypt_data(config, token, expires_at)
            
            # Verify we can parse it manually
            offset = 0
            config_len = struct.unpack('>I', encrypted[offset:offset+4])[0]
            offset += 4
            config_data = json.loads(encrypted[offset:offset+config_len].decode('utf-8'))
            offset += config_len
            
            token_len = struct.unpack('>I', encrypted[offset:offset+4])[0]
            offset += 4
            token_data = encrypted[offset:offset+token_len].decode('utf-8')
            offset += token_len
            
            expires_data = struct.unpack('>Q', encrypted[offset:offset+8])[0]
            
            assert config_data == config
            assert token_data == token
            assert expires_data == expires_at

    def test_decrypt_invalid_data(self, temp_dir):
        """Test decryption of invalid/corrupted data."""
        with patch('acdown.auth.get_app_data_dir', return_value=temp_dir):
            auth = AuthManager()
            
            with pytest.raises(Exception):
                auth._decrypt_data(b'invalid_data')


class TestDataPersistence:
    """Test saving and loading data from disk."""

    def test_save_and_load_data(self, temp_dir, mock_auth_data):
        """Test complete save and load cycle."""
        with patch('acdown.auth.get_app_data_dir', return_value=temp_dir):
            auth = AuthManager()
            
            config = mock_auth_data['config']
            token = mock_auth_data['token']
            expires_at = mock_auth_data['expiresAt']
            
            # Save data
            auth._save_data(config, token, expires_at)
            
            # Verify file exists
            assert auth.data_file.exists()
            
            # Load data
            loaded = auth._load_data()
            
            assert loaded['config'] == config
            assert loaded['token'] == token
            assert loaded['expiresAt'] == expires_at

    def test_load_nonexistent_file(self, temp_dir):
        """Test loading when data file doesn't exist."""
        with patch('acdown.auth.get_app_data_dir', return_value=temp_dir):
            auth = AuthManager()
            
            with pytest.raises(FileNotFoundError):
                auth._load_data()

    def test_file_permissions(self, temp_dir):
        """Test that saved file has restrictive permissions."""
        with patch('acdown.auth.get_app_data_dir', return_value=temp_dir):
            auth = AuthManager()
            
            auth._save_data({}, 'token', 0)
            
            # Check file permissions (should be 600)
            mode = auth.data_file.stat().st_mode & 0o777
            assert mode == 0o600


class TestLogin:
    """Test authentication login functionality."""

    @pytest.mark.asyncio
    async def test_login_success(self, temp_dir):
        """Test successful login with TOTP code."""
        with patch('acdown.auth.get_app_data_dir', return_value=temp_dir):
            auth = AuthManager()
            
            # Set server URL first
            auth.set_config('server_url', 'http://test-server:3000')
            
            # Mock response
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                'success': True,
                'data': {
                    'token': 'new_token_123',
                    'expiresAt': 9999999999999
                }
            }
            
            with patch('httpx.AsyncClient') as mock_client_class:
                mock_client = AsyncMock()
                mock_client.post = AsyncMock(return_value=mock_response)
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=None)
                mock_client_class.return_value = mock_client
                
                result = await auth.login('123456')
                
                assert result['token'] == 'new_token_123'
                assert auth.get_token() == 'new_token_123'

    @pytest.mark.asyncio
    async def test_login_no_server_url(self, temp_dir):
        """Test login fails when server URL not configured."""
        with patch('acdown.auth.get_app_data_dir', return_value=temp_dir):
            auth = AuthManager()
            
            with pytest.raises(Exception) as exc_info:
                await auth.login('123456')
            
            assert "Server URL not configured" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_login_failure(self, temp_dir):
        """Test login with invalid credentials."""
        with patch('acdown.auth.get_app_data_dir', return_value=temp_dir):
            auth = AuthManager()
            auth.set_config('server_url', 'http://test-server:3000')
            
            # Mock error response
            mock_response = MagicMock()
            mock_response.status_code = 401
            mock_response.text = 'Unauthorized'
            mock_response.json.return_value = {
                'success': False,
                'error': {
                    'code': 'TOTP_INVALID',
                    'message': 'Invalid TOTP code'
                }
            }
            
            with patch('httpx.AsyncClient') as mock_client_class:
                mock_client = AsyncMock()
                mock_client.post = AsyncMock(return_value=mock_response)
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=None)
                mock_client_class.return_value = mock_client
                
                with pytest.raises(Exception) as exc_info:
                    await auth.login('invalid_code')
                
                assert "Authentication failed" in str(exc_info.value)


class TestTokenValidation:
    """Test token validation functionality."""

    def test_is_token_valid_with_valid_token(self, temp_dir, mock_auth_data):
        """Test validation of non-expired token."""
        with patch('acdown.auth.get_app_data_dir', return_value=temp_dir):
            auth = AuthManager()
            
            # Save valid token
            auth._save_data(
                mock_auth_data['config'],
                mock_auth_data['token'],
                mock_auth_data['expiresAt']
            )
            
            assert auth.is_token_valid() is True

    def test_is_token_valid_with_expired_token(self, temp_dir):
        """Test validation of expired token."""
        with patch('acdown.auth.get_app_data_dir', return_value=temp_dir):
            auth = AuthManager()
            
            # Save expired token (past timestamp)
            past_time = int(time.time() * 1000) - 1000000
            auth._save_data({}, 'old_token', past_time)
            
            assert auth.is_token_valid() is False

    def test_is_token_valid_with_empty_token(self, temp_dir):
        """Test validation when no token exists."""
        with patch('acdown.auth.get_app_data_dir', return_value=temp_dir):
            auth = AuthManager()
            
            assert auth.is_token_valid() is False

    def test_is_token_valid_no_file(self, temp_dir):
        """Test validation when data file doesn't exist."""
        with patch('acdown.auth.get_app_data_dir', return_value=temp_dir):
            auth = AuthManager()
            
            assert auth.is_token_valid() is False


class TestConfiguration:
    """Test configuration management."""

    def test_set_and_get_config(self, temp_dir):
        """Test setting and retrieving configuration values."""
        with patch('acdown.auth.get_app_data_dir', return_value=temp_dir):
            auth = AuthManager()
            
            # Set various config values
            auth.set_config('server_url', 'http://example.com:3000')
            auth.set_config('parallel', 5)
            auth.set_config('verbose', 'true')
            auth.set_config('output', '/tmp/downloads')
            
            # Retrieve values
            assert auth.get_config_value('server_url') == 'http://example.com:3000'
            assert auth.get_config_value('parallel') == 5
            assert auth.get_config_value('verbose') is True
            assert auth.get_config_value('output') == '/tmp/downloads'

    def test_config_type_conversion(self, temp_dir):
        """Test automatic type conversion for config values."""
        with patch('acdown.auth.get_app_data_dir', return_value=temp_dir):
            auth = AuthManager()
            
            # Test parallel (int conversion)
            auth.set_config('parallel', '10')
            assert auth.get_config_value('parallel') == 10
            assert isinstance(auth.get_config_value('parallel'), int)
            
            # Test verbose (bool conversion)
            auth.set_config('verbose', 'yes')
            assert auth.get_config_value('verbose') is True
            
            auth.set_config('verbose', 'false')
            assert auth.get_config_value('verbose') is False

    def test_get_full_config_with_defaults(self, temp_dir):
        """Test getting full config merged with defaults."""
        with patch('acdown.auth.get_app_data_dir', return_value=temp_dir):
            auth = AuthManager()
            
            # Set only one value
            auth.set_config('server_url', 'http://custom.com')
            
            config = auth.get_config()
            
            assert config['server_url'] == 'http://custom.com'
            assert config['parallel'] == 3  # default
            assert config['verbose'] is False  # default
            assert config['output'] == '.'  # default

    def test_get_config_no_file(self, temp_dir):
        """Test getting config when no file exists."""
        with patch('acdown.auth.get_app_data_dir', return_value=temp_dir):
            auth = AuthManager()
            
            config = auth.get_config()
            
            assert config == auth.default_config

    def test_get_config_value_default(self, temp_dir):
        """Test getting individual config value with default."""
        with patch('acdown.auth.get_app_data_dir', return_value=temp_dir):
            auth = AuthManager()
            
            # Not set, should return default
            assert auth.get_config_value('parallel') == 3
            assert auth.get_config_value('verbose') is False


class TestServerURL:
    """Test server URL configuration checks."""

    def test_is_server_url_configured_true(self, temp_dir):
        """Test when server URL is configured."""
        with patch('acdown.auth.get_app_data_dir', return_value=temp_dir):
            auth = AuthManager()
            auth.set_config('server_url', 'http://server.com:3000')
            
            assert auth.is_server_url_configured() is True

    def test_is_server_url_configured_false_empty(self, temp_dir):
        """Test when server URL is empty."""
        with patch('acdown.auth.get_app_data_dir', return_value=temp_dir):
            auth = AuthManager()
            
            assert auth.is_server_url_configured() is False

    def test_is_server_url_configured_false_whitespace(self, temp_dir):
        """Test when server URL is only whitespace."""
        with patch('acdown.auth.get_app_data_dir', return_value=temp_dir):
            auth = AuthManager()
            auth.set_config('server_url', '   ')
            
            assert auth.is_server_url_configured() is False


class TestLogout:
    """Test logout functionality."""

    def test_logout_clears_token_keeps_config(self, temp_dir):
        """Test that logout clears token but preserves config."""
        with patch('acdown.auth.get_app_data_dir', return_value=temp_dir):
            auth = AuthManager()
            
            # Set config and token
            auth.set_config('server_url', 'http://server.com')
            auth.set_config('parallel', 5)
            auth._save_data(
                {'server_url': 'http://server.com', 'parallel': 5},
                'active_token',
                9999999999999
            )
            
            # Logout
            auth.logout()
            
            # Config should remain
            assert auth.get_config_value('server_url') == 'http://server.com'
            assert auth.get_config_value('parallel') == 5
            
            # Token should be cleared
            assert auth.get_token() == ''
            assert auth.is_token_valid() is False

    def test_logout_no_file(self, temp_dir):
        """Test logout when no data file exists."""
        with patch('acdown.auth.get_app_data_dir', return_value=temp_dir):
            auth = AuthManager()
            
            # Should not raise exception
            auth.logout()


class TestGetToken:
    """Test token retrieval."""

    def test_get_token_valid(self, temp_dir, mock_auth_data):
        """Test getting a valid token."""
        with patch('acdown.auth.get_app_data_dir', return_value=temp_dir):
            auth = AuthManager()
            
            auth._save_data(
                mock_auth_data['config'],
                mock_auth_data['token'],
                mock_auth_data['expiresAt']
            )
            
            assert auth.get_token() == 'test_token_12345'

    def test_get_token_no_file(self, temp_dir):
        """Test getting token when file doesn't exist."""
        with patch('acdown.auth.get_app_data_dir', return_value=temp_dir):
            auth = AuthManager()
            
            assert auth.get_token() == ''
