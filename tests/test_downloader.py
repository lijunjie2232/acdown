"""Tests for the download engine."""

import pytest
import asyncio
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock, call, ANY
import tempfile
import shutil

from acdown.downloader import Downloader


class TestDownloaderInit:
    """Test Downloader initialization."""

    def test_init_with_valid_config(self):
        """Test initialization with valid configuration."""
        config = {
            'server_url': 'http://test-server:3000',
            'parallel': 5,
            'verbose': True,
            'output': '/tmp/downloads'
        }
        
        downloader = Downloader(config)
        
        assert downloader.server_url == 'http://test-server:3000'
        assert downloader.concurrent == 5
        assert downloader.verbose is True
        assert downloader.default_output == '/tmp/downloads'
        assert downloader.max_retries == 3

    def test_init_with_default_config(self):
        """Test initialization with minimal config uses defaults."""
        config = {'server_url': 'http://test-server:3000'}
        
        downloader = Downloader(config)
        
        assert downloader.concurrent == 3
        assert downloader.verbose is False
        assert downloader.default_output == '.'

    def test_init_without_server_url_raises_error(self):
        """Test that missing server URL raises ValueError."""
        config = {'parallel': 3}
        
        with pytest.raises(ValueError) as exc_info:
            Downloader(config)
        
        assert "Server URL not configured" in str(exc_info.value)


class TestAnalyzeFile:
    """Test file analysis functionality."""

    @pytest.mark.asyncio
    async def test_analyze_file_success(self):
        """Test successful file analysis."""
        config = {'server_url': 'http://test-server:3000'}
        downloader = Downloader(config)
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'success': True,
            'data': {
                'fileSize': 1048576,
                'totalParts': 2,
                'chunkSize': 524288,
                'parts': ['part1', 'part2']
            }
        }
        
        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client
            
            result = await downloader.analyze_file('https://example.com/file.zip', 'token123')
            
            assert result['fileSize'] == 1048576
            assert result['totalParts'] == 2
            assert len(result['parts']) == 2
            
            # Verify API call
            mock_client.post.assert_called_once_with(
                'http://test-server:3000/api/proxy/analyze',
                json={'url': 'https://example.com/file.zip'},
                headers={
                    'x-auth-token': 'token123',
                    'Authorization': 'Bearer token123'
                }
            )

    @pytest.mark.asyncio
    async def test_analyze_file_failure(self):
        """Test file analysis with server error."""
        config = {'server_url': 'http://test-server:3000'}
        downloader = Downloader(config)
        
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = 'Internal Server Error'
        
        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client
            
            with pytest.raises(Exception) as exc_info:
                await downloader.analyze_file('https://example.com/file.zip', 'token123')
            
            assert "Analysis failed" in str(exc_info.value)


class TestDownloadPart:
    """Test individual part download."""

    @pytest.mark.asyncio
    async def test_download_part_success(self, temp_dir):
        """Test successful download of a single part."""
        config = {'server_url': 'http://test-server:3000'}
        downloader = Downloader(config)
        
        # Mock streaming response
        mock_response = MagicMock()
        mock_response.status_code = 206
        
        # Create async iterator for chunks
        async def mock_stream(chunk_size=65536):
            yield b'chunk1'
            yield b'chunk2'
        
        mock_response.aiter_bytes = mock_stream
        
        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_context = AsyncMock()
            mock_context.__aenter__ = AsyncMock(return_value=mock_response)
            mock_context.__aexit__ = AsyncMock(return_value=None)
            mock_client.stream = MagicMock(return_value=mock_context)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client
            
            part_file = await downloader.download_part(
                'encrypted_params',
                'token123',
                0,
                temp_dir,
                'test.zip',
                expected_size=12  # chunk1chunk2 length
            )
            
            assert part_file.exists()
            assert part_file.name == 'test.zip.0'
            assert part_file.read_bytes() == b'chunk1chunk2'

    @pytest.mark.asyncio
    async def test_download_part_skip_existing(self, temp_dir):
        """Test skipping download if part already exists with correct size."""
        config = {'server_url': 'http://test-server:3000', 'verbose': True}
        downloader = Downloader(config)
        
        base_filename = 'skip_test.zip'
        part_index = 0
        expected_size = 10
        part_file = temp_dir / f'{base_filename}.{part_index}'
        part_file.write_bytes(b'0123456789')
        
        mock_tracker = MagicMock()
        
        # Should not call httpx.AsyncClient if skipped
        with patch('httpx.AsyncClient') as mock_client_class:
            result = await downloader.download_part(
                'params', 'token', part_index, temp_dir, base_filename,
                progress_tracker=mock_tracker, expected_size=expected_size
            )
            
            assert result == part_file
            assert mock_client_class.call_count == 0
            mock_tracker.update_progress.assert_called_once_with(expected_size, part_index + 1, 0)

    @pytest.mark.asyncio
    async def test_download_part_with_retry(self, temp_dir):
        """Test part download with retry on failure."""
        config = {'server_url': 'http://test-server:3000', 'verbose': True}
        downloader = Downloader(config)
        
        call_count = 0
        
        async def mock_stream(chunk_size=65536):
            yield b'data'
        
        async def side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise Exception("Network error")
            
            # Success on 3rd attempt
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
            
            # Mock sleep to speed up test
            with patch('asyncio.sleep'):
                part_file = await downloader.download_part(
                    'encrypted_params',
                    'token123',
                    0,
                    temp_dir,
                    'test.zip'
                )
                
                assert part_file.exists()
                assert call_count == 3  # Failed twice, succeeded on third

    @pytest.mark.asyncio
    async def test_download_part_max_retries_exceeded(self, temp_dir):
        """Test part download fails after max retries."""
        config = {'server_url': 'http://test-server:3000'}
        downloader = Downloader(config)
        
        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_context = AsyncMock()
            mock_context.__aenter__ = AsyncMock(side_effect=Exception("Persistent error"))
            mock_context.__aexit__ = AsyncMock(return_value=None)
            mock_client.stream = MagicMock(return_value=mock_context)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client
            
            with patch('asyncio.sleep'):
                with pytest.raises(Exception) as exc_info:
                    await downloader.download_part(
                        'encrypted_params',
                        'token123',
                        0,
                        temp_dir,
                        'test.zip'
                    )
                
                assert "Persistent error" in str(exc_info.value)


class TestDownloadParts:
    """Test concurrent part downloads."""

    @pytest.mark.asyncio
    async def test_download_parts_concurrent(self, temp_dir):
        """Test downloading multiple parts concurrently."""
        config = {'server_url': 'http://test-server:3000', 'parallel': 2}
        downloader = Downloader(config)
        
        parts = ['part1_encrypted', 'part2_encrypted', 'part3_encrypted']
        
        # Mock download_part to return immediately
        async def mock_download_part(*args, **kwargs):
            part_index = args[2]
            part_file = temp_dir / f'part_{part_index}'
            part_file.write_bytes(f'content_{part_index}'.encode())
            return part_file
        
        with patch.object(downloader, 'download_part', side_effect=mock_download_part):
            with patch('acdown.downloader.downloader.ProgressTracker'
):
                part_files = await downloader.download_parts(
                    parts,
                    'token123',
                    temp_dir,
                    3072,  # total_size
                    3,      # total_parts
                    'test.zip'
                )
                
                assert len(part_files) == 3
                for i, part_file in enumerate(part_files):
                    assert part_file.exists()
                    assert part_file.read_bytes() == f'content_{i}'.encode()


    @pytest.mark.asyncio
    async def test_download_parts_thread_id_assignment(self, temp_dir):
        """Test that download_parts correctly assigns thread IDs to tasks."""
        config = {'server_url': 'http://test-server:3000', 'parallel': 2}
        downloader = Downloader(config)
        
        parts = ['part1', 'part2', 'part3']
        
        # Track which thread IDs were used
        used_thread_ids = []
        
        async def mock_download_part(*args, **kwargs):
            thread_id = kwargs.get('thread_id')
            used_thread_ids.append(thread_id)
            part_index = args[2]
            return temp_dir / f'part_{part_index}'
        
        mock_tracker = MagicMock()
        
        with patch.object(downloader, 'download_part', side_effect=mock_download_part):
            with patch('acdown.downloader.downloader.ProgressTracker'
, return_value=mock_tracker):
                await downloader.download_parts(
                    parts,
                    'token123',
                    temp_dir,
                    3000,
                    3,
                    'test.zip',
                    show_individual_progress=True,
                    chunk_size=1000
                )
                
                # Verify thread IDs are within [0, parallel-1]
                assert all(0 <= tid < 2 for tid in used_thread_ids)
                assert len(used_thread_ids) == 3
                
                # Verify start_part was called for each part
                assert mock_tracker.start_part.call_count == 3
                
                # Verify chunk_size was used for start_part
                # Calls are: (thread_id, part_number, part_size)
                # Part 1: (tid, 1, 1000)
                # Part 2: (tid, 2, 1000)
                # Part 3: (tid, 3, 1000) - since total_size=3000, 3*1000=3000
                mock_tracker.start_part.assert_has_calls([
                    call(ANY, 1, 1000),
                    call(ANY, 2, 1000),
                    call(ANY, 3, 1000)
                ], any_order=True)

class TestConcatenateParts:
    """Test part concatenation."""

    def test_concatenate_parts_basic(self, temp_dir):
        """Test basic concatenation of parts."""
        config = {'server_url': 'http://test-server:3000'}
        downloader = Downloader(config)
        
        # Create test part files
        part1 = temp_dir / 'part_0'
        part2 = temp_dir / 'part_1'
        part3 = temp_dir / 'part_2'
        
        part1.write_bytes(b'AAA')
        part2.write_bytes(b'BBB')
        part3.write_bytes(b'CCC')
        
        output_file = temp_dir / 'final_file.bin'
        
        downloader.concatenate_parts([part1, part2, part3], output_file)
        
        assert output_file.exists()
        assert output_file.read_bytes() == b'AAABBBCCC'

    def test_concatenate_parts_empty(self, temp_dir):
        """Test concatenation with no parts."""
        config = {'server_url': 'http://test-server:3000'}
        downloader = Downloader(config)
        
        output_file = temp_dir / 'empty_file.bin'
        
        downloader.concatenate_parts([], output_file)
        
        assert output_file.exists()
        assert output_file.read_bytes() == b''


class TestFullDownload:
    """Test complete download workflow."""

    @pytest.mark.asyncio
    async def test_download_complete_workflow(self, temp_dir):
        """Test full download from analysis to completion."""
        config = {
            'server_url': 'http://test-server:3000',
            'parallel': 2,
            'verbose': False,
            'output': str(temp_dir)
        }
        downloader = Downloader(config)
        
        url = 'https://example.com/test.zip'
        token = 'test_token'
        
        # Mock analyze_file
        file_info = {
            'fileSize': 1024,
            'totalParts': 2,
            'chunkSize': 512,
            'parts': ['part1', 'part2']
        }
        
        # Mock download_parts
        part1 = temp_dir / 'part_0'
        part2 = temp_dir / 'part_1'
        part1.write_bytes(b'PART1')
        part2.write_bytes(b'PART2')
        
        output_path = temp_dir / 'test.zip'
        
        with patch.object(downloader, 'analyze_file', return_value=file_info):
            with patch.object(downloader, 'download_parts', return_value=[part1, part2]):
                with patch('acdown.utils.check_disk_space', return_value=True):
                    result = await downloader.download(url, None, token)
                    
                    assert result == output_path
                    assert result.exists()
                    assert result.read_bytes() == b'PART1PART2'
                    
                    # Temp files should be cleaned up
                    assert not part1.exists()
                    assert not part2.exists()

    @pytest.mark.asyncio
    async def test_download_with_custom_output(self, temp_dir):
        """Test download with custom output path."""
        config = {'server_url': 'http://test-server:3000'}
        downloader = Downloader(config)
        
        custom_output = temp_dir / 'custom' / 'directory' / 'file.bin'
        
        file_info = {
            'fileSize': 100,
            'totalParts': 1,
            'chunkSize': 100,
            'parts': ['part1']
        }
        
        part_file = temp_dir / 'part_0'
        part_file.write_bytes(b'data')
        
        with patch.object(downloader, 'analyze_file', return_value=file_info):
            with patch.object(downloader, 'download_parts', return_value=[part_file]):
                with patch('acdown.utils.check_disk_space', return_value=True):
                    result = await downloader.download(
                        'https://example.com/file.bin',
                        str(custom_output),
                        'token'
                    )
                    
                    assert result == custom_output
                    assert custom_output.parent.exists()

    @pytest.mark.asyncio
    async def test_download_insufficient_disk_space(self, temp_dir):
        """Test download fails when disk space is insufficient."""
        config = {'server_url': 'http://test-server:3000'}
        downloader = Downloader(config)
        
        file_info = {
            'fileSize': 999999999999,  # Very large
            'totalParts': 1,
            'chunkSize': 999999999999,
            'parts': ['part1']
        }
        
        with patch.object(downloader, 'analyze_file', return_value=file_info):
            with patch('acdown.utils.check_disk_space', return_value=False):
                with pytest.raises(Exception) as exc_info:
                    await downloader.download(
                        'https://example.com/file.bin',
                        None,
                        'token'
                    )
                
                assert "Insufficient disk space" in str(exc_info.value)
