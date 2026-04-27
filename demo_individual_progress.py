#!/usr/bin/env python3
"""Demo script showing individual progress bars for download threads."""

import asyncio
from pathlib import Path
from acdown.progress import ProgressTracker


async def demo_individual_progress():
    """Demonstrate individual progress bars for multiple download threads."""
    
    print("=" * 60)
    print("Individual Progress Bars Demo")
    print("=" * 60)
    print()
    
    # Simulate downloading a file with 5 parts
    total_size = 10_000_000  # 10 MB
    total_parts = 5
    
    # Initialize progress tracker with individual progress enabled
    tracker = ProgressTracker(total_size, total_parts, show_individual=True)
    tracker.init_progress_bar("demo_file.zip")
    
    # Simulate concurrent downloads
    async def simulate_part_download(part_index, part_size):
        """Simulate downloading a single part."""
        chunk_size = part_size // 10  # Download in 10 chunks
        
        for i in range(10):
            await asyncio.sleep(0.1)  # Simulate network delay
            tracker.update_progress(chunk_size, part_index + 1)
    
    # Create tasks for all parts (simulating concurrent downloads)
    part_sizes = [2_000_000, 2_000_000, 2_000_000, 2_000_000, 2_000_000]
    tasks = [
        simulate_part_download(i, size) 
        for i, size in enumerate(part_sizes)
    ]
    
    # Run all downloads concurrently
    await asyncio.gather(*tasks)
    
    # Close progress tracker
    tracker.close()
    
    print()
    print("=" * 60)
    print("Download Complete!")
    print(f"Total downloaded: {tracker.format_size(tracker.downloaded_size)}")
    print(f"Average speed: {tracker.format_size(int(tracker.get_speed()))}/s")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(demo_individual_progress())
