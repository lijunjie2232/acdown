"""Test fixtures and utilities for ACDown tests."""

import pytest
import tempfile
import shutil
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
import asyncio
import json
import struct


@pytest.fixture
def temp_dir():
    """Create a temporary directory for test files."""
    temp = tempfile.mkdtemp()
    yield Path(temp)
    shutil.rmtree(temp)


@pytest.fixture
def mock_auth_data():
    """Create mock authentication data."""
    return {
        'config': {
            'server_url': 'http://test-server:3000',
            'parallel': 3,
            'verbose': False,
            'output': '.'
        },
        'token': 'test_token_12345',
        'expiresAt': 9999999999999  # Far future
    }


@pytest.fixture
def mock_file_info():
    """Create mock file analysis response."""
    return {
        'fileSize': 1048576,  # 1 MB
        'totalParts': 2,
        'chunkSize': 524288,  # 512 KB
        'parts': [
            'cGFydDE=:ZW5jcnlwdGVk...',
            'cGFydDI=:bW9yZSBlbmM...'
        ]
    }


@pytest.fixture
def sample_binary_data(mock_auth_data):
    """Create binary data in the format used by AuthManager."""
    config_json = json.dumps(mock_auth_data['config']).encode('utf-8')
    token_bytes = mock_auth_data['token'].encode('utf-8')
    
    return (
        struct.pack('>I', len(config_json)) +
        config_json +
        struct.pack('>I', len(token_bytes)) +
        token_bytes +
        struct.pack('>Q', mock_auth_data['expiresAt'])
    )


@pytest.fixture
def event_loop():
    """Create an instance of the default event loop for each test."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def mock_httpx_client():
    """Mock httpx.AsyncClient for testing."""
    with patch('httpx.AsyncClient') as mock_client:
        yield mock_client


@pytest.fixture
def mock_console():
    """Mock Rich Console for testing."""
    with patch('acdown.downloader.Console') as mock_console:
        yield mock_console


@pytest.fixture
def mock_progress_tracker():
    """Mock ProgressTracker for testing."""
    with patch('acdown.downloader.ProgressTracker') as mock_tracker:
        yield mock_tracker
