"""Tests for progress tracking."""

import pytest
import time
from unittest.mock import patch, MagicMock

from acdown.progress import ProgressTracker


class TestProgressTrackerInit:
    """Test ProgressTracker initialization."""

    def test_init_basic(self):
        """Test basic initialization."""
        tracker = ProgressTracker(1048576, 2)  # 1 MB, 2 parts
        
        assert tracker.total_size == 1048576
        assert tracker.total_parts == 2
        assert tracker.downloaded_size == 0
        assert tracker.start_time is not None

    def test_init_with_different_sizes(self):
        """Test initialization with various file sizes."""
        # Small file
        tracker1 = ProgressTracker(1024, 1)
        assert tracker1.total_size == 1024
        
        # Large file
        tracker2 = ProgressTracker(1073741824, 10)  # 1 GB
        assert tracker2.total_size == 1073741824


class TestProgressBar:
    """Test progress bar initialization and management."""

    def test_init_progress_bar(self):
        """Test progress bar initialization."""
        tracker = ProgressTracker(1048576, 2)
        
        with patch('acdown.progress.progress.Progress') as mock_progress_class:
            mock_progress = MagicMock()
            mock_progress_class.return_value = mock_progress
            
            tracker.init_progress_bar("test_file.zip")
            
            mock_progress_class.assert_called_once()
            mock_progress.start.assert_called_once()
            mock_progress.add_task.assert_called_once()
            
            # Verify task was added with correct total
            call_args = mock_progress.add_task.call_args
            assert call_args[0][0] == "test_file.zip"
            assert call_args[1]['total'] == 1048576

    def test_close_progress_bar(self):
        """Test progress bar cleanup."""
        tracker = ProgressTracker(1048576, 2)
        
        with patch('acdown.progress.progress.Progress') as mock_progress_class:
            mock_progress = MagicMock()
            mock_progress_class.return_value = mock_progress
            
            tracker.init_progress_bar()
            tracker.close()
            
            mock_progress.stop.assert_called_once()

    def test_close_without_init(self):
        """Test closing progress bar that was never initialized."""
        tracker = ProgressTracker(1048576, 2)
        
        # Should not raise exception
        tracker.close()


class TestProgressUpdates:
    """Test progress update functionality."""

    def test_update_progress_basic(self):
        """Test basic progress update."""
        tracker = ProgressTracker(1000, 2)
        
        with patch('acdown.progress.progress.Progress') as mock_progress_class:
            mock_progress = MagicMock()
            mock_progress_class.return_value = mock_progress
            
            tracker.init_progress_bar()
            tracker.update_progress(100, 1)
            
            assert tracker.downloaded_size == 100
            mock_progress.update.assert_called_once()
            
            # Verify update parameters
            call_args = mock_progress.update.call_args
            assert call_args[1]['advance'] == 100

    def test_update_progress_multiple_times(self):
        """Test multiple progress updates accumulate correctly."""
        tracker = ProgressTracker(1000, 2)
        
        with patch('acdown.progress.progress.Progress') as mock_progress_class:
            mock_progress = MagicMock()
            mock_progress_class.return_value = mock_progress
            
            tracker.init_progress_bar()
            
            tracker.update_progress(100, 1)
            assert tracker.downloaded_size == 100
            
            tracker.update_progress(200, 1)
            assert tracker.downloaded_size == 300
            
            tracker.update_progress(500, 2)
            assert tracker.downloaded_size == 800

    def test_update_progress_with_part_number(self):
        """Test progress update with part number (legacy mode)."""
        tracker = ProgressTracker(1000, 3)
        
        with patch('acdown.progress.progress.Progress') as mock_progress_class:
            mock_progress = MagicMock()
            mock_progress_class.return_value = mock_progress
            
            tracker.init_progress_bar()
            tracker.update_progress(100, 2)
            
            # Verify description includes part number in legacy single-bar mode
            call_args = mock_progress.update.call_args
            assert 'Part 2/3' in call_args[1]['description']

    def test_start_part(self):
        """Test start_part method updates description and resets progress."""
        tracker = ProgressTracker(1000, 4, show_individual=True)
        
        with patch('acdown.progress.progress.Progress') as mock_progress_class:
            mock_progress = MagicMock()
            mock_progress_class.return_value = mock_progress
            
            tracker.init_progress_bar("test.bin", num_threads=2)
            
            # Start part 1 on thread 0
            tracker.start_part(0, 1, 250)
            
            # Verify reset and update called
            mock_progress.reset.assert_called_once()
            call_args = mock_progress.update.call_args
            assert call_args[1]['total'] == 250
            assert "Thread 1 (Part 1)" in call_args[1]['description']


class TestSpeedCalculation:
    """Test download speed calculations."""

    def test_get_speed_initial(self):
        """Test speed calculation at start (no time elapsed)."""
        tracker = ProgressTracker(1000, 1)
        
        # Immediately after init, speed should be 0 or very small
        speed = tracker.get_speed()
        assert speed >= 0

    def test_get_speed_after_download(self):
        """Test speed calculation after some data downloaded."""
        tracker = ProgressTracker(1000, 1)
        
        # Simulate some time passing
        time.sleep(0.1)
        tracker.update_progress(500, 1)
        
        speed = tracker.get_speed()
        assert speed > 0
        # Speed should be approximately 500 bytes / 0.1 seconds = 5000 bytes/s
        # Allow for timing variations
        assert speed < 10000  # Upper bound check

    def test_get_speed_zero_when_no_data(self):
        """Test speed is zero when no data downloaded."""
        tracker = ProgressTracker(1000, 1)
        
        speed = tracker.get_speed()
        assert speed == 0


class TestETACalculation:
    """Test ETA (Estimated Time of Arrival) calculations."""

    def test_get_eta_initial(self):
        """Test ETA at start."""
        tracker = ProgressTracker(1000, 1)
        
        eta = tracker.get_eta()
        # At start with no speed, ETA should be 0
        assert eta == 0

    def test_get_eta_after_download(self):
        """Test ETA calculation during download."""
        tracker = ProgressTracker(1000, 1)
        
        # Download half the file
        tracker.update_progress(500, 1)
        
        # Simulate time passing to establish speed
        time.sleep(0.1)
        tracker.update_progress(100, 1)
        
        eta = tracker.get_eta()
        # Should have a positive ETA
        assert eta >= 0

    def test_get_eta_complete(self):
        """Test ETA when download is complete."""
        tracker = ProgressTracker(1000, 1)
        
        # Download everything
        tracker.update_progress(1000, 1)
        time.sleep(0.1)
        
        eta = tracker.get_eta()
        # When complete, ETA should be 0 or negative
        assert eta <= 0


class TestFormatSize:
    """Test file size formatting."""

    def test_format_bytes(self):
        """Test formatting byte values."""
        tracker = ProgressTracker(1000, 1)
        
        assert tracker.format_size(0) == "0.00 B"
        assert tracker.format_size(100) == "100.00 B"
        assert tracker.format_size(1023) == "1023.00 B"

    def test_format_kilobytes(self):
        """Test formatting kilobyte values."""
        tracker = ProgressTracker(1000, 1)
        
        assert tracker.format_size(1024) == "1.00 KB"
        assert tracker.format_size(2048) == "2.00 KB"
        assert tracker.format_size(5120) == "5.00 KB"

    def test_format_megabytes(self):
        """Test formatting megabyte values."""
        tracker = ProgressTracker(1000, 1)
        
        assert tracker.format_size(1048576) == "1.00 MB"  # 1 MB
        assert tracker.format_size(5242880) == "5.00 MB"  # 5 MB

    def test_format_gigabytes(self):
        """Test formatting gigabyte values."""
        tracker = ProgressTracker(1000, 1)
        
        assert tracker.format_size(1073741824) == "1.00 GB"  # 1 GB

    def test_format_terabytes(self):
        """Test formatting terabyte values."""
        tracker = ProgressTracker(1000, 1)
        
        assert tracker.format_size(1099511627776) == "1.00 TB"  # 1 TB

    def test_format_large_values(self):
        """Test formatting very large values."""
        tracker = ProgressTracker(1000, 1)
        
        # Petabytes
        result = tracker.format_size(1125899906842624)
        assert "PB" in result


class TestIndividualProgressBars:
    """Test individual progress bars for concurrent threads."""

    def test_init_with_multiple_threads(self):
        """Test initialization with multiple thread progress bars."""
        tracker = ProgressTracker(1048576, 4, show_individual=True)
        
        with patch('acdown.progress.progress.Progress') as mock_progress_class:
            mock_progress = MagicMock()
            mock_progress_class.return_value = mock_progress
            
            # Initialize with 3 concurrent threads
            tracker.init_progress_bar("test_file.zip", num_threads=3)
            
            # Should create 1 overall task + 3 thread tasks = 4 tasks total
            assert mock_progress.add_task.call_count == 4
            
            # Verify thread tasks were created
            assert len(tracker.thread_tasks) == 3

    def test_update_thread_progress(self):
        """Test updating progress for specific thread."""
        tracker = ProgressTracker(1000, 4, show_individual=True)
        
        with patch('acdown.progress.progress.Progress') as mock_progress_class:
            mock_progress = MagicMock()
            mock_progress_class.return_value = mock_progress
            
            tracker.init_progress_bar("test.bin", num_threads=2)
            
            # Update progress for thread 0
            tracker.update_progress(100, current_part=1, thread_id=0)
            
            # Should have 2 updates: one for thread, one for overall
            assert mock_progress.update.call_count == 2
            
            # Verify thread update has advance but not necessarily description (moved to start_part)
            calls = mock_progress.update.call_args_list
            thread_call = calls[0]
            assert thread_call[1]['advance'] == 100

    def test_update_multiple_threads(self):
        """Test updating progress for multiple threads simultaneously."""
        tracker = ProgressTracker(1000, 4, show_individual=True)
        
        with patch('acdown.progress.progress.Progress') as mock_progress_class:
            mock_progress = MagicMock()
            mock_progress_class.return_value = mock_progress
            
            tracker.init_progress_bar("test.bin", num_threads=3)
            
            # Simulate concurrent downloads from different threads
            tracker.update_progress(100, current_part=1, thread_id=0)
            tracker.update_progress(150, current_part=2, thread_id=1)
            tracker.update_progress(200, current_part=3, thread_id=2)
            
            # Total should be sum of all updates
            assert tracker.downloaded_size == 450
            
            # Each update creates 2 calls (thread + overall), so 6 total
            assert mock_progress.update.call_count == 6

    def test_thread_progress_without_show_individual(self):
        """Test that thread_id is ignored when show_individual is False."""
        tracker = ProgressTracker(1000, 4, show_individual=False)
        
        with patch('acdown.progress.progress.Progress') as mock_progress_class:
            mock_progress = MagicMock()
            mock_progress_class.return_value = mock_progress
            
            tracker.init_progress_bar("test.bin", num_threads=3)
            
            # Update with thread_id should still work but use single progress bar
            tracker.update_progress(100, current_part=1, thread_id=0)
            
            # Should only have 1 update call (overall progress only)
            assert mock_progress.update.call_count == 1


class TestIntegration:
    """Integration tests for ProgressTracker."""

    def test_full_download_simulation(self):
        """Simulate a complete download with progress tracking."""
        total_size = 1048576  # 1 MB
        total_parts = 4
        tracker = ProgressTracker(total_size, total_parts)
        
        with patch('acdown.progress.progress.Progress') as mock_progress_class:
            mock_progress = MagicMock()
            mock_progress_class.return_value = mock_progress
            
            tracker.init_progress_bar("test.bin")
            
            # Simulate downloading parts
            part_sizes = [262144, 262144, 262144, 262144]  # 256 KB each
            
            for i, size in enumerate(part_sizes, 1):
                time.sleep(0.01)  # Small delay
                tracker.update_progress(size, i)
            
            # Verify final state
            assert tracker.downloaded_size == total_size
            
            # Check speed and ETA
            speed = tracker.get_speed()
            assert speed > 0
            
            eta = tracker.get_eta()
            assert eta >= 0
            
            tracker.close()
            mock_progress.stop.assert_called_once()

    def test_progress_with_varying_chunk_sizes(self):
        """Test progress tracking with non-uniform chunk sizes."""
        tracker = ProgressTracker(1000, 3)
        
        with patch('acdown.progress.progress.Progress') as mock_progress_class:
            mock_progress = MagicMock()
            mock_progress_class.return_value = mock_progress
            
            tracker.init_progress_bar()
            
            # Variable chunk sizes
            tracker.update_progress(100, 1)
            tracker.update_progress(500, 2)
            tracker.update_progress(400, 3)
            
            assert tracker.downloaded_size == 1000
