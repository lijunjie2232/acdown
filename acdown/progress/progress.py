"""Progress tracking module using Rich for beautiful terminal output."""

from rich.progress import Progress, BarColumn, TextColumn, DownloadColumn, TransferSpeedColumn, TimeRemainingColumn
from rich.console import Console
import time


class ProgressTracker:
    """Tracks download progress with Rich progress bars."""

    def __init__(self, total_size: int, total_parts: int, show_individual: bool = False):
        """Initialize progress tracker.
        
        Args:
            total_size: Total file size in bytes
            total_parts: Number of file parts/chunks
            show_individual: If True, show individual progress bars for each part/thread
        """
        self.total_size = total_size
        self.total_parts = total_parts
        self.downloaded_size = 0
        self.start_time = time.time()
        self.console = Console()
        self.progress = None
        self.task_id = None
        self.show_individual = show_individual
        self.part_tasks = {}  # Track individual part task IDs
        self.part_sizes = {}  # Track expected size for each part
        self.thread_tasks = {}  # Track tasks for each concurrent thread

    def init_progress_bar(self, filename: str = "Downloading", num_threads: int = 1):
        """Initialize Rich progress bar with multiple columns.
        
        Args:
            filename: Name of the file being downloaded (for display)
            num_threads: Number of concurrent threads/parts to show
        """
        self.progress = Progress(
            TextColumn("[bold blue]{task.description}"),
            BarColumn(bar_width=None),
            "[progress.percentage]{task.percentage:>3.1f}%",
            "•",
            DownloadColumn(),
            "•",
            TransferSpeedColumn(),
            "•",
            TimeRemainingColumn(),
            console=self.console,
            expand=True
        )
        self.progress.start()
        
        if self.show_individual:
            # Create overall progress bar first
            self.task_id = self.progress.add_task(f"[bold]{filename}[/bold]", total=self.total_size)
            
            # Create individual progress bars for each thread/part
            for i in range(num_threads):
                # Initial state for threads
                task_id = self.progress.add_task(f"Thread {i+1}", total=None, visible=True)
                self.thread_tasks[i] = task_id
        else:
            # Single progress bar for overall download
            self.task_id = self.progress.add_task(filename, total=self.total_size)

    def start_part(self, thread_id: int, part_number: int, part_size: int):
        """Reset a thread's progress bar for a new part.
        
        Args:
            thread_id: ID of the thread (0-indexed)
            part_number: Part number being started (1-indexed)
            part_size: Size of the part in bytes
        """
        if self.progress and self.show_individual and thread_id in self.thread_tasks:
            task_id = self.thread_tasks[thread_id]
            self.progress.reset(task_id)
            self.progress.update(
                task_id,
                total=part_size,
                description=f"Thread {thread_id + 1} (Part {part_number})"
            )

    def update_progress(self, bytes_downloaded: int, current_part: int = 0, thread_id: int = 0):
        """Update progress with newly downloaded bytes.
        
        Args:
            bytes_downloaded: Number of bytes downloaded in this update
            current_part: Current part number being downloaded (1-indexed)
            thread_id: ID of the thread downloading this part (0-indexed)
        """
        self.downloaded_size += bytes_downloaded
        if self.progress and self.task_id is not None:
            if self.show_individual:
                # Update thread-specific progress bar
                if thread_id in self.thread_tasks:
                    self.progress.update(
                        self.thread_tasks[thread_id],
                        advance=bytes_downloaded
                    )
                # Update overall progress
                self.progress.update(
                    self.task_id,
                    advance=bytes_downloaded
                )
            else:
                # Legacy single progress bar mode
                self.progress.update(
                    self.task_id,
                    advance=bytes_downloaded,
                    description=f"Part {current_part}/{self.total_parts}" if current_part > 0 else "Downloading"
                )

    def close(self):
        """Close and cleanup progress bar."""
        if self.progress:
            self.progress.stop()

    def get_speed(self) -> float:
        """Calculate current download speed in bytes per second.
        
        Returns:
            Download speed in bytes/second
        """
        elapsed = time.time() - self.start_time
        if elapsed > 0:
            return self.downloaded_size / elapsed
        return 0

    def get_eta(self) -> float:
        """Calculate estimated time remaining in seconds.
        
        Returns:
            ETA in seconds, or 0 if cannot calculate
        """
        speed = self.get_speed()
        if speed > 0:
            remaining = self.total_size - self.downloaded_size
            return remaining / speed
        return 0

    def format_size(self, size_bytes: int) -> str:
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
