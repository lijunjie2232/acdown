"""Demo script showing multi-threaded progress bars with Rich."""

import asyncio
import time
from acdown.progress import ProgressTracker


async def simulate_download():
    """Simulate a multi-threaded download with individual progress bars."""
    
    # Configuration
    total_size = 10 * 1024 * 1024  # 10 MB
    num_parts = 10
    num_threads = 3
    
    print("Starting simulated download with multi-threaded progress bars...")
    print(f"Total size: {total_size / (1024*1024):.1f} MB")
    print(f"Number of parts: {num_parts}")
    print(f"Concurrent threads: {num_threads}\n")
    
    # Initialize progress tracker with individual progress bars
    tracker = ProgressTracker(total_size, num_parts, show_individual=True)
    tracker.init_progress_bar("demo_file.zip", num_threads=num_threads)
    
    try:
        # Simulate concurrent downloads
        tasks = []
        for thread_id in range(num_threads):
            task = asyncio.create_task(
                simulate_thread(thread_id, num_parts, tracker)
            )
            tasks.append(task)
        
        # Wait for all threads to complete
        await asyncio.gather(*tasks)
        
    finally:
        tracker.close()
    
    print("\n✓ Download simulation complete!")


async def simulate_thread(thread_id: int, num_parts: int, tracker: ProgressTracker):
    """Simulate a single download thread."""
    
    # Each thread downloads multiple parts
    parts_per_thread = num_parts // 3
    part_size = 1024 * 1024  # 1 MB per part
    
    for part_num in range(parts_per_thread):
        current_part = thread_id * parts_per_thread + part_num + 1
        
        # Notify tracker that a new part is starting
        tracker.start_part(thread_id, current_part, part_size)
        
        # Simulate downloading chunks within this part
        chunks = 10
        chunk_size = part_size // chunks
        
        for _ in range(chunks):
            # Simulate network delay
            await asyncio.sleep(0.05)
            
            # Update progress
            tracker.update_progress(
                bytes_downloaded=chunk_size,
                current_part=current_part,
                thread_id=thread_id
            )


if __name__ == "__main__":
    asyncio.run(simulate_download())
