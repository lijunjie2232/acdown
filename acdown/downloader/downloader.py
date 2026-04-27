"""Download engine for ACDown client with chunked, concurrent downloads."""

import httpx
import asyncio
import logging
from pathlib import Path
from typing import List, Optional
from rich.console import Console

from acdown.progress import ProgressTracker
from acdown.utils import check_disk_space, get_logger


class Downloader:
    """Handles file download with chunked, concurrent downloading support."""

    def __init__(self, config: dict):
        """Initialize downloader with configuration.
        
        Args:
            config: Configuration dictionary with server_url, parallel, verbose settings
        """
        self.server_url = config.get('server_url', '')
        self.concurrent = config.get('parallel', 3)
        self.verbose = config.get('verbose', False)
        self.default_output = config.get('output', '.')
        self.max_retries = 3
        self.console = Console()
        self.logger = get_logger("downloader")
        
        if not self.server_url:
            raise ValueError("Server URL not configured. Please run: acdown config set server_url <url>")

    async def download(self, url: str, output_path: Optional[str], token: str,
                      show_individual_progress: bool = False) -> Path:
        """Main download method orchestrating the entire download process.
        
        Args:
            url: URL to download
            output_path: Output file path (None to auto-detect from URL)
            token: Authentication token
            show_individual_progress: If True, show individual progress bars for each part
            
        Returns:
            Path to the downloaded file
            
        Raises:
            Exception: If download fails
        """
        # 1. Analyze file
        if self.verbose:
            self.console.print(f"[cyan]Analyzing file:[/cyan] {url}")
            self.logger.debug(f"Analyzing URL: {url}")
        file_info = await self.analyze_file(url, token)
        
        total_size = file_info['fileSize']
        total_parts = file_info['totalParts']
        
        if self.verbose:
            from acdown.utils import format_size
            self.console.print(f"[cyan]File size:[/cyan] {format_size(total_size)} ({total_parts} parts)")
            self.logger.debug(f"File size: {total_size} bytes, Parts: {total_parts}")
        
        # 2. Determine output path
        if output_path:
            output_file = Path(output_path)
        else:
            from acdown.utils import extract_filename_from_url
            filename = extract_filename_from_url(url)
            output_file = Path(self.default_output) / filename
        
        # Make sure parent directory exists
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        # 3. Check disk space
        if not check_disk_space(output_file, total_size):
            raise Exception(f"Insufficient disk space. Need {total_size} bytes")
        
        # 4. Download parts (concurrently)
        # Enable individual progress by default if concurrent > 1
        if self.concurrent > 1 and not show_individual_progress:
            show_individual_progress = True
            
        part_files = await self.download_parts(
            file_info['parts'], 
            token, 
            output_file.parent,
            total_size,
            total_parts,
            output_file.name,
            show_individual_progress,
            file_info.get('chunkSize', 0)
        )
        
        # 5. Concatenate parts
        if self.verbose:
            self.console.print("[cyan]Concatenating parts...[/cyan]")
        self.concatenate_parts(part_files, output_file)
        
        # 6. Cleanup temp files
        for part_file in part_files:
            part_file.unlink()
        
        return output_file

    async def analyze_file(self, url: str, token: str) -> dict:
        """Analyze file through server to get metadata and parts.
        
        Args:
            url: URL to analyze
            token: Authentication token
            
        Returns:
            Dictionary with fileSize, totalParts, chunkSize, and parts
            
        Raises:
            Exception: If analysis fails
        """
        async with httpx.AsyncClient() as client:
            # Try both header formats for compatibility
            headers = {
                'x-auth-token': token,
                'Authorization': f'Bearer {token}'
            }
            if self.verbose:
                self.console.print(f"[cyan]Sending request with headers:[/cyan]")
                self.logger.debug(f"Request headers: {headers}")
            
            response = await client.post(
                f'{self.server_url}/api/proxy/analyze',
                json={'url': url},
                headers=headers
            )
            if response.status_code == 200:
                return response.json()['data']
            else:
                error_msg = response.text
                try:
                    error_data = response.json()
                    if 'error' in error_data:
                        error_msg = error_data['error'].get('message', response.text)
                except:
                    pass
                raise Exception(f"Analysis failed: {error_msg}")

    async def download_part(self, encrypted_params: str, token: str, 
                           part_index: int, output_dir: Path,
                           base_filename: str,
                           progress_tracker: Optional[ProgressTracker] = None,
                           thread_id: int = 0) -> Path:
        """Download single part with retry logic.
        
        Args:
            encrypted_params: Encrypted parameters for this part
            token: Authentication token
            part_index: Index of this part (for naming)
            output_dir: Directory to save part file
            base_filename: Base name of the final file for tmp naming
            progress_tracker: Optional progress tracker to update
            thread_id: ID of the thread downloading this part (0-indexed)
            
        Returns:
            Path to downloaded part file
            
        Raises:
            Exception: If download fails after all retries
        """
        part_file = output_dir / f'{base_filename}.tmp.{part_index}'
        
        for attempt in range(1, self.max_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=60.0) as client:
                    # Use both header formats for compatibility
                    headers = {
                        'x-auth-token': token,
                        'Authorization': f'Bearer {token}'
                    }
                    async with client.stream(
                        'GET',
                        f'{self.server_url}/api/proxy/part/{encrypted_params}',
                        headers=headers
                    ) as response:
                        if response.status_code == 206 or response.status_code == 200:
                            with open(part_file, 'wb') as f:
                                async for chunk in response.aiter_bytes(chunk_size=65536):
                                    f.write(chunk)
                                    if progress_tracker:
                                        progress_tracker.update_progress(len(chunk), part_index + 1, thread_id)
                            return part_file
                        else:
                            raise Exception(f"HTTP {response.status_code}")
            except Exception as e:
                if attempt == self.max_retries:
                    raise e
                if self.verbose:
                    self.console.print(f"[yellow]Retrying part {part_index + 1}... (attempt {attempt + 1}/{self.max_retries})[/yellow]")
                await asyncio.sleep(2 * attempt)  # Exponential backoff

    async def download_parts(self, parts: List[str], token: str, 
                            output_dir: Path, total_size: int, total_parts: int,
                            base_filename: str,
                            show_individual_progress: bool = False,
                            chunk_size: int = 0) -> List[Path]:
        """Download all parts with concurrency control and progress tracking.
        
        Args:
            parts: List of encrypted parameter strings for each part
            token: Authentication token
            output_dir: Directory to save part files
            total_size: Total file size for progress tracking
            total_parts: Total number of parts
            base_filename: Base name of the final file for tmp naming
            show_individual_progress: If True, show individual progress bars for each part
            chunk_size: Size of each chunk (except possibly the last one)
            
        Returns:
            List of paths to downloaded part files
        """
        # Initialize progress tracker with number of concurrent threads
        num_threads = min(self.concurrent, len(parts))
        progress_tracker = ProgressTracker(total_size, total_parts, show_individual=show_individual_progress)
        progress_tracker.init_progress_bar(base_filename, num_threads=num_threads)
        
        semaphore = asyncio.Semaphore(self.concurrent)
        # Create a pool of available thread IDs
        thread_id_queue = asyncio.Queue()
        for i in range(num_threads):
            thread_id_queue.put_nowait(i)
        
        async def download_with_semaphore(part, index):
            async with semaphore:
                # Acquire a thread ID
                thread_id = await thread_id_queue.get()
                try:
                    # Calculate part size for the progress bar
                    current_part_size = chunk_size
                    if index == total_parts - 1 and chunk_size > 0:
                        current_part_size = total_size - (chunk_size * (total_parts - 1))
                    
                    # Notify tracker that a new part is starting on this thread
                    if show_individual_progress and current_part_size > 0:
                        progress_tracker.start_part(thread_id, index + 1, current_part_size)
                        
                    return await self.download_part(
                        part, token, index, output_dir, base_filename,
                        progress_tracker, thread_id=thread_id
                    )
                finally:
                    # Release the thread ID back to the pool
                    thread_id_queue.put_nowait(thread_id)
        
        try:
            tasks = [download_with_semaphore(part, i) for i, part in enumerate(parts)]
            part_files = await asyncio.gather(*tasks)
            return list(part_files)
        finally:
            progress_tracker.close()

    def concatenate_parts(self, part_files: List[Path], output_file: Path):
        """Concatenate all part files into the final output file.
        
        Args:
            part_files: List of part file paths in order
            output_file: Path to the final output file
        """
        with open(output_file, 'wb') as outfile:
            for part_file in part_files:
                with open(part_file, 'rb') as infile:
                    # Read in chunks to avoid loading entire file into memory
                    while True:
                        chunk = infile.read(65536)  # 64KB chunks
                        if not chunk:
                            break
                        outfile.write(chunk)
