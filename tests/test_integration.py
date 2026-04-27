"""Integration tests for complete ACDown workflows."""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock
import tempfile
import shutil

from acdown.auth import AuthManager
from acdown.downloader import Downloader


class TestAuthenticationWorkflow:
    """Test complete authentication workflow."""

    @pytest.mark.asyncio
    async def test_full_auth_workflow(self, temp_dir):
        """Test complete authentication flow from setup to validation."""
        with patch('acdown.auth.auth.get_app_data_dir', return_value=temp_dir):
            auth = AuthManager()
            
            # Initially no server URL configured
            assert auth.is_server_url_configured() is False
            assert auth.is_token_valid() is False
            
            # Configure server URL
            auth.set_config('server_url', 'http://test-server:3000')
            assert auth.is_server_url_configured() is True
            
            # Mock successful login
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                'success': True,
                'data': {
                    'token': 'authenticated_token',
                    'expiresAt': 9999999999999
                }
            }
            
            with patch('httpx.AsyncClient') as mock_client_class:
                mock_client = AsyncMock()
                mock_client.post = AsyncMock(return_value=mock_response)
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=None)
                mock_client_class.return_value = mock_client
                
                # Login
                result = await auth.login('123456')
                
                assert result['token'] == 'authenticated_token'
                assert auth.is_token_valid() is True
                assert auth.get_token() == 'authenticated_token'
                
                # Logout
                auth.logout()
                
                assert auth.is_token_valid() is False
                assert auth.get_token() == ''
                # Config should persist
                assert auth.is_server_url_configured() is True


class TestDownloadWorkflow:
    """Test complete download workflow."""

    @pytest.mark.asyncio
    async def test_full_download_workflow(self, temp_dir):
        """Test complete download from analysis to file creation."""
        config = {
            'server_url': 'http://test-server:3000',
            'parallel': 2,
            'verbose': False,
            'output': str(temp_dir)
        }
        downloader = Downloader(config)
        
        url = 'https://example.com/test.zip'
        token = 'test_token'
        
        # Create mock part files
        part1 = temp_dir / 'part_0.tmp'
        part2 = temp_dir / 'part_1.tmp'
        part1.write_bytes(b'PART1_DATA')
        part2.write_bytes(b'PART2_DATA')
        
        expected_output = temp_dir / 'test.zip'
        
        # Mock analyze_file
        file_info = {
            'fileSize': 20,
            'totalParts': 2,
            'chunkSize': 10,
            'parts': ['encrypted_part1', 'encrypted_part2']
        }
        
        with patch.object(downloader, 'analyze_file', return_value=file_info):
            with patch.object(downloader, 'download_parts', return_value=[part1, part2]):
                with patch('acdown.utils.check_disk_space', return_value=True):
                    result = await downloader.download(url, None, token)
                    
                    assert result == expected_output
                    assert result.exists()
                    assert result.read_bytes() == b'PART1_DATAPART2_DATA'
                    
                    # Temp files cleaned up
                    assert not part1.exists()
                    assert not part2.exists()


class TestConfigPersistence:
    """Test configuration persistence across operations."""

    def test_config_persists_across_instances(self, temp_dir):
        """Test that config persists when creating new AuthManager instances."""
        with patch('acdown.auth.auth.get_app_data_dir', return_value=temp_dir):
            # First instance - set config
            auth1 = AuthManager()
            auth1.set_config('server_url', 'http://persistent-server:3000')
            auth1.set_config('parallel', 7)
            auth1._save_data(
                {'server_url': 'http://persistent-server:3000', 'parallel': 7},
                'test_token',
                9999999999999
            )
            
            # Second instance - should load same config
            auth2 = AuthManager()
            config = auth2.get_config()
            
            assert config['server_url'] == 'http://persistent-server:3000'
            assert config['parallel'] == 7
            assert auth2.get_token() == 'test_token'


class TestErrorRecovery:
    """Test error handling and recovery scenarios."""

    @pytest.mark.asyncio
    async def test_retry_on_network_error(self, temp_dir):
        """Test that downloads retry on network errors."""
        config = {'server_url': 'http://test-server:3000'}
        downloader = Downloader(config)
        
        call_count = 0
        
        async def mock_stream(chunk_size=65536):
            yield b'success_data'
        
        async def side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise Exception("Network timeout")
            
            # Success on second attempt
            mock_response = MagicMock()
            mock_response.status_code = 206
            mock_response.aiter_bytes = mock_stream
            return mock_response
        
        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_context = AsyncMock()
            mock_context.__aenter__ = side_effect
            mock_context.__aexit__ = AsyncMock(return_value=None)
            mock_client.stream = MagicMock(return_value=mock_context)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client
            
            with patch('asyncio.sleep'):
                part_file = await downloader.download_part(
                    'encrypted_params',
                    'token',
                    0,
                    temp_dir,
                    'test.zip'
                )
                
                assert part_file.exists()
                assert call_count == 2  # Failed once, succeeded on second

    def test_graceful_handling_of_corrupted_data(self, temp_dir):
        """Test graceful handling of corrupted data file."""
        with patch('acdown.auth.auth.get_app_data_dir', return_value=temp_dir):
            auth = AuthManager()
            
            # Write corrupted data
            auth.data_file.write_bytes(b'corrupted_data_that_cannot_be_parsed')
            
            # Should handle gracefully and return defaults
            config = auth.get_config()
            assert config == auth.default_config
            
            token = auth.get_token()
            assert token == ''
            
            is_valid = auth.is_token_valid()
            assert is_valid is False


class TestConcurrentDownloads:
    """Test concurrent download functionality."""

    @pytest.mark.asyncio
    async def test_concurrent_part_downloads(self, temp_dir):
        """Test that parts are downloaded concurrently."""
        config = {'server_url': 'http://test-server:3000', 'parallel': 3}
        downloader = Downloader(config)
        
        parts = ['part1', 'part2', 'part3', 'part4', 'part5']
        download_order = []
        
        async def mock_download_part(*args, **kwargs):
            part_index = args[2]
            download_order.append(part_index)
            
            # Simulate varying download times
            import asyncio
            await asyncio.sleep(0.01 * (part_index % 3))
            
            part_file = temp_dir / f'part_{part_index}.tmp'
            part_file.write_bytes(f'data_{part_index}'.encode())
            return part_file
        
        with patch.object(downloader, 'download_part', side_effect=mock_download_part):
            with patch('acdown.downloader.ProgressTracker'):
                part_files = await downloader.download_parts(
                    parts,
                    'token',
                    temp_dir,
                    500,  # total_size
                    5,     # total_parts
                    'test.zip'
                )
                
                assert len(part_files) == 5
                
                # With concurrency, order might not be sequential
                # But all parts should be downloaded
                for i in range(5):
                    assert any(f'part_{i}.tmp' in str(pf) for pf in part_files)


class TestDataIntegrity:
    """Test data integrity throughout the workflow."""

    def test_binary_serialization_integrity(self, temp_dir):
        """Test that binary serialization preserves data integrity."""
        with patch('acdown.auth.auth.get_app_data_dir', return_value=temp_dir):
            auth = AuthManager()
            
            test_configs = [
                {'server_url': 'http://simple.com'},
                {'server_url': 'http://complex.com:8080/path', 'parallel': 10, 'verbose': True},
                {'output': '/very/long/path/with/special-chars_测试'},
            ]
            
            for config in test_configs:
                token = f'token_{len(config)}'
                expires_at = 1234567890
                
                # Save
                auth._save_data(config, token, expires_at)
                
                # Load
                loaded = auth._load_data()
                
                assert loaded['config'] == config
                assert loaded['token'] == token
                assert loaded['expiresAt'] == expires_at

    def test_file_concatenation_integrity(self, temp_dir):
        """Test that file concatenation preserves data integrity."""
        config = {'server_url': 'http://test-server:3000'}
        downloader = Downloader(config)
        
        # Create test parts with known content
        num_parts = 10
        part_files = []
        expected_content = b''
        
        for i in range(num_parts):
            part_file = temp_dir / f'part_{i}.tmp'
            content = bytes([i] * 100)  # 100 bytes of value i
            part_file.write_bytes(content)
            expected_content += content
            part_files.append(part_file)
        
        output_file = temp_dir / 'combined.bin'
        downloader.concatenate_parts(part_files, output_file)
        
        # Verify integrity
        assert output_file.read_bytes() == expected_content
        assert len(output_file.read_bytes()) == num_parts * 100
