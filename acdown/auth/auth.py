"""Authentication and configuration management module."""

import httpx
import struct
import json
import time
from pathlib import Path
from typing import Optional

from acdown.utils import get_app_data_dir


class AuthManager:
    """Manages authentication tokens and configuration for ACDown client."""

    def __init__(self):
        """Initialize AuthManager with default settings."""
        # Use system app data directory for cross-platform compatibility
        self.app_dir = get_app_data_dir("acdown")
        self.data_file = self.app_dir / 'data.bin'
        # Default configuration - server URL must be configured by user
        self.default_config = {
            'server_url': '',  # Empty by default, user must configure
            'parallel': 3,
            'verbose': False,
            'output': '.'
        }

    def _encrypt_data(self, config: dict, token: str, expires_at: int) -> bytes:
        """Serialize config and token to binary format.
        
        Format: [config_len(4)][config_json][token_len(4)][token][expires_at(8)]
        
        Args:
            config: Configuration dictionary
            token: Authentication token string
            expires_at: Token expiration timestamp in milliseconds
            
        Returns:
            Binary data containing serialized config and token
        """
        # Serialize config to JSON bytes
        config_json = json.dumps(config).encode('utf-8')
        token_bytes = token.encode('utf-8')
        
        # Format: [config_len(4)][config_json][token_len(4)][token][expires_at(8)]
        return (
            struct.pack('>I', len(config_json)) +
            config_json +
            struct.pack('>I', len(token_bytes)) +
            token_bytes +
            struct.pack('>Q', expires_at)
        )

    def _decrypt_data(self, data: bytes) -> dict:
        """Deserialize config and token from binary format.
        
        Args:
            data: Binary data containing serialized config and token
            
        Returns:
            Dictionary with config, token, and expiresAt keys
            
        Raises:
            ValueError: If data format is invalid
        """
        offset = 0
        
        # Read config
        config_len = struct.unpack('>I', data[offset:offset+4])[0]
        offset += 4
        config_json = data[offset:offset+config_len].decode('utf-8')
        config = json.loads(config_json)
        offset += config_len
        
        # Read Token
        token_len = struct.unpack('>I', data[offset:offset+4])[0]
        offset += 4
        token = data[offset:offset+token_len].decode('utf-8')
        offset += token_len
        
        # Read expires_at
        expires_at = struct.unpack('>Q', data[offset:offset+8])[0]
        
        return {'config': config, 'token': token, 'expiresAt': expires_at}

    def _save_data(self, config: dict, token: str, expires_at: int):
        """Save data to binary file with restrictive permissions.
        
        Args:
            config: Configuration dictionary
            token: Authentication token string
            expires_at: Token expiration timestamp in milliseconds
        """
        data = self._encrypt_data(config, token, expires_at)
        self.data_file.write_bytes(data)
        self.data_file.chmod(0o600)  # Restrictive permissions

    def _load_data(self) -> dict:
        """Load data from binary file.
        
        Returns:
            Dictionary with config, token, and expiresAt keys
            
        Raises:
            FileNotFoundError: If data file doesn't exist
        """
        if not self.data_file.exists():
            raise FileNotFoundError("No authentication data found")
        data = self.data_file.read_bytes()
        return self._decrypt_data(data)

    async def login(self, totp_code: str) -> dict:
        """Authenticate with TOTP code and save token.
        
        Args:
            totp_code: 6-digit TOTP code
            
        Returns:
            Dictionary with token and expiresAt
            
        Raises:
            Exception: If authentication fails
        """
        config = self.get_config()
        base_url = config.get('server_url', self.default_config['server_url'])
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f'{base_url}/api/auth/login',
                json={'totpCode': totp_code}
            )
            if response.status_code == 200:
                data = response.json()['data']
                # Save both config and token
                self._save_data(config, data['token'], data['expiresAt'])
                return data
            else:
                error_msg = response.text
                try:
                    error_data = response.json()
                    if 'error' in error_data:
                        error_msg = error_data['error'].get('message', response.text)
                except:
                    pass
                raise Exception(f"Authentication failed: {error_msg}")

    def is_token_valid(self) -> bool:
        """Check if stored token is still valid.
        
        Returns:
            True if token exists and hasn't expired, False otherwise
        """
        try:
            data = self._load_data()
            token = data.get('token', '')
            if not token:
                return False
            return data['expiresAt'] > int(time.time() * 1000)
        except:
            return False

    def set_config(self, key: str, value):
        """Set a configuration value.
        
        Args:
            key: Configuration key (url, parallel, verbose, output)
            value: Configuration value
        """
        try:
            data = self._load_data()
            config = data.get('config', {})
            token = data.get('token', '')
            expires_at = data.get('expiresAt', 0)
        except:
            config = {}
            token = ''
            expires_at = 0
        
        # Update config value with type conversion
        if key == 'parallel':
            config[key] = int(value)
        elif key == 'verbose':
            config[key] = value.lower() in ('true', '1', 'yes')
        else:
            config[key] = value
        
        # Save updated config
        self._save_data(config, token, expires_at)

    def get_config_value(self, key: str):
        """Get a specific configuration value.
        
        Args:
            key: Configuration key
            
        Returns:
            Configuration value or default if not set
        """
        try:
            data = self._load_data()
            config = data.get('config', {})
            return config.get(key, self.default_config.get(key))
        except:
            return self.default_config.get(key)

    def get_config(self) -> dict:
        """Get full configuration with defaults merged.
        
        Returns:
            Complete configuration dictionary with defaults
        """
        try:
            data = self._load_data()
            config = data.get('config', {})
            # Merge with defaults
            return {**self.default_config, **config}
        except:
            return self.default_config.copy()

    def get_token(self) -> str:
        """Get stored authentication token.
        
        Returns:
            Token string or empty string if not available
        """
        try:
            data = self._load_data()
            return data.get('token', '')
        except:
            return ''

    def is_server_url_configured(self) -> bool:
        """Check if server URL has been configured by user.
        
        Returns:
            True if URL is set and not empty, False otherwise
        """
        config = self.get_config()
        url = config.get('server_url', '')
        return bool(url and url.strip())

    def logout(self):
        """Clear authentication data but keep configuration."""
        try:
            config = self.get_config()
            # Save config with empty token
            self._save_data(config, '', 0)
        except:
            # If file doesn't exist, just remove it
            if self.data_file.exists():
                self.data_file.unlink()
