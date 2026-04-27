#!/usr/bin/env python3
"""Demo script showing ACDown Client features."""

import subprocess
import sys

def run_command(cmd, description):
    """Run a command and display results."""
    print(f"\n{'='*60}")
    print(f"📋 {description}")
    print(f"{'='*60}")
    print(f"$ {' '.join(cmd)}")
    print()
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    print(result.stdout)
    if result.stderr:
        print(result.stderr)
    
    return result.returncode == 0

def main():
    """Run demo commands."""
    print("🚀 ACDown Client Demo")
    print("=" * 60)
    
    # Test 1: Show help
    run_command(
        ["uv", "run", "python", "main.py", "--help"],
        "Main Help"
    )
    
    # Test 2: Config - Set URL
    run_command(
        ["uv", "run", "python", "main.py", "config", "set", "server_url", "http://localhost:3000"],
        "Configure Server URL"
    )
    
    # Test 3: Config - Set parallel downloads
    run_command(
        ["uv", "run", "python", "main.py", "config", "set", "parallel", "5"],
        "Set Parallel Downloads"
    )
    
    # Test 4: Config - Get all settings
    run_command(
        ["uv", "run", "python", "main.py", "config", "get"],
        "View All Configuration"
    )
    
    # Test 5: Try download without auth (should fail gracefully)
    run_command(
        ["uv", "run", "python", "main.py", "download", "https://example.com/test.zip"],
        "Download Without Authentication (Expected Error)"
    )
    
    # Test 6: Invalid URL test
    run_command(
        ["uv", "run", "python", "main.py", "download", "not-a-url"],
        "Invalid URL Test (Expected Error)"
    )
    
    # Test 7: Logout
    run_command(
        ["uv", "run", "python", "main.py", "logout"],
        "Logout (Clear Token)"
    )
    
    print("\n" + "=" * 60)
    print("✅ Demo Complete!")
    print("=" * 60)
    print("\nTo use ACDown Client:")
    print("1. Set server URL: acdown config set server_url <your-server>")
    print("2. Authenticate: acdown auth <totp-code>")
    print("3. Download files: acdown download <url> [options]")
    print("\nSee README.md for complete documentation.")

if __name__ == "__main__":
    main()
