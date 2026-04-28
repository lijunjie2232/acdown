# ACDown Client

A powerful command-line download client for ACDown Server with chunked, authenticated downloads.

## Features

- 🔐 **Secure Authentication**: TOTP-based authentication with token caching
- ⚡ **Concurrent Downloads**: Download file chunks in parallel for maximum speed
- 📊 **Beautiful Progress**: Rich progress bars with speed and ETA tracking
  - Multi-line progress display for concurrent downloads (optional)
  - Individual thread progress bars showing real-time download status
- 🔄 **Auto Retry**: Automatic retry with exponential backoff on failures
- 💾 **Smart Storage**: Binary format storage for better security
- ⚙️ **Configurable**: Flexible configuration for server URL, concurrency, and more
- 🎯 **Streaming**: Memory-efficient streaming downloads

## Installation

### Prerequisites

- Python 3.13 or higher
- [uv](https://github.com/astral-sh/uv) package manager (recommended)

### Setup

```bash
# Clone the repository
git clone <repository-url>
cd acdown-client

# Create virtual environment and install dependencies
uv sync

# Activate virtual environment (optional, uv run handles this)
source .venv/bin/activate  # On Linux/macOS
```

## Quick Start

### 1. Configure Server URL (Required)

```bash
# Set your ACDown server URL (required before first use)
acdown config set server_url http://your-server:3000
```

**Note**: The server URL must be configured before using any other commands. The application will prompt you if it's not set.

### 2. Authenticate

```bash
# Get a TOTP code from your authenticator app
acdown auth 123456
```

### 3. Download Files

```bash
# Simple download
acdown https://example.com/file.zip

# Download with custom output path
acdown https://example.com/file.zip -o ./downloads/myfile.zip

# Download with custom concurrency
acdown https://example.com/large-file.iso -c 5

# Verbose mode
acdown https://example.com/file.zip -v
```

## Commands Reference

### Download Files

```bash
acdown <url> [OPTIONS]
```

**Arguments:**
- `URL`: The URL to download (required)

**Options:**
- `-o, --output PATH`: Output file path (default: extract from URL)
- `-c, --concurrent INT`: Number of concurrent downloads (default: 3)
- `-v, --verbose`: Enable verbose logging
- `-ip, --individual-progress`: Show individual progress bars for each download thread
- `--help`: Show help message

**Examples:**

```bash
# Basic download
acdown https://github.com/example/app/releases/download/v1.0/app.zip

# Custom output location
acdown https://example.com/file.iso -o ~/Downloads/file.iso

# High concurrency for fast connection
acdown https://example.com/huge-file.zip -c 10

# Show individual progress bars for each concurrent thread
acdown https://example.com/large-file.zip -c 5 --individual-progress

# Debug mode
acdown https://example.com/file.zip -v
```

### Authentication

```bash
acdown auth <totp-code>
```

Authenticate with the ACDown server using a 6-digit TOTP code.

**Example:**
```bash
acdown auth 654321
```

**Output:**
```
╭─────────────────────────────────────╮
│         Authentication              │
├─────────────────────────────────────┤
│ ✓ Authentication successful         │
│                                     │
│ Server URL: http://localhost:3000   │
│ Token saved to: data.bin            │
│ Expires: 2024-01-02 15:30:00        │
╰─────────────────────────────────────╯
```

### Configuration Management

```bash
acdown config <action> [key] [value]
```

Manage server configuration settings.

**Actions:**
- `set <key> <value>`: Set a configuration value
- `get [key]`: Get configuration value(s)

**Configuration Keys:**
- `server_url`: ACDown server base URL (**required**, no default)
- `parallel`: Number of concurrent downloads (default: 3)
- `verbose`: Enable verbose logging (default: false)
- `output`: Default output directory (default: .)

**Examples:**

```bash
# Set ACDown server URL
acdown config set server_url http://myserver.com:3000

# Set concurrent downloads
acdown config set parallel 5

# Enable verbose mode
acdown config set verbose true

# Set default output directory
acdown config set output ./downloads

# Get specific config value
acdown config get server_url

# Get all configuration
acdown config get
```

### Logout

```bash
acdown logout
```

Clear the saved authentication token while keeping configuration.

**Output:**
```
╭─────────────────────────────────────╮
│            Logout                   │
├─────────────────────────────────────┤
│ ✓ Logged out successfully           │
│                                     │
│ Authentication token has been       │
│ cleared.                            │
╰─────────────────────────────────────╯
```

## Usage Scenarios

### Scenario 1: First-Time Setup

```bash
# 1. Set server URL
acdown config set server_url http://my-acdown-server.com:3000

# 2. Authenticate
acdown auth 123456

# 3. Download a file
acdown https://example.com/software.zip
```

### Scenario 2: Large File Download

```bash
# Use high concurrency for large files
acdown https://example.com/ubuntu-24.04.iso -c 8 -o ~/Downloads/ubuntu.iso
```

### Scenario 3: Batch Downloads

```bash
# Create a script for multiple downloads
for url in $(cat urls.txt); do
    acdown "$url" -o ./downloads/
done
```

### Scenario 4: Debugging Issues

```bash
# Enable verbose mode to see detailed information
acdown https://example.com/file.zip -v
```

## Configuration Storage

All configuration and authentication data is stored in `data.bin` using a secure binary format.

### Storage Location

The data file is stored in the system's application data directory:

- **Linux**: `~/.local/share/acdown/data.bin`
- **macOS**: `~/Library/Application Support/acdown/data.bin`
- **Windows**: `C:\Users\<username>\AppData\Local\acdown\data.bin`

### Binary Format

```
[config_length(4 bytes)][config_json][token_length(4 bytes)][token][expires_at(8 bytes)]
```

The file has restrictive permissions (600) for security.

## Error Handling

The client handles various error scenarios gracefully:

- **Network Errors**: Automatic retry with exponential backoff (max 3 retries)
- **Authentication Errors**: Clear messages when token is expired or invalid
- **Invalid URLs**: Validation before attempting download
- **Server Errors**: Detailed error messages from server responses
- **Disk Space**: Pre-check before starting download
- **Interruption**: Graceful cleanup on Ctrl+C

### Common Error Messages

```
✗ Authentication failed
  Error: Invalid TOTP code
  Hint: TOTP codes expire every 30 seconds

✗ Download failed
  Error: Connection timeout
  Retrying... (attempt 2/3)

✗ Not authenticated. Please run 'acdown auth <code>' first.
```

## Performance Tips

1. **Increase Concurrency**: For fast connections, increase concurrent downloads
   ```bash
   acdown config set parallel 8
   ```

2. **Use Verbose Mode**: Monitor download details
   ```bash
   acdown <url> -v
   ```

3. **Check Server Health**: Ensure server is running before downloading
   ```bash
   curl http://your-server:3000/health
   ```

## Troubleshooting

### Authentication Issues

**Problem**: "Not authenticated" error

**Solution**:
```bash
# Re-authenticate with fresh TOTP code
acdown auth <new-code>
```

### Connection Issues

**Problem**: Connection timeout or refused

**Solutions**:
1. Check server is running: `curl http://server:3000/health`
2. Verify server URL: `acdown config get url`
3. Check network connectivity

### Download Failures

**Problem**: Download fails repeatedly

**Solutions**:
1. Enable verbose mode: `acdown <url> -v`
2. Reduce concurrency: `acdown <url> -c 1`
3. Check disk space
4. Verify URL is accessible

### Token Expiration

**Problem**: Token expires frequently

**Solution**: Tokens have a fixed lifetime set by the server. Re-authenticate when needed:
```bash
acdown auth <new-code>
```

## Architecture

```
acdown/
├── acdown/                 # Main package
│   ├── __init__.py        # Package exports
│   ├── cli.py             # CLI commands (Typer)
│   ├── auth.py            # Authentication manager
│   ├── downloader.py      # Download engine
│   ├── progress.py        # Progress tracking
│   ├── logger.py          # Logging configuration
│   └── utils.py           # Utility functions
├── config.example.toml    # Example configuration
├── pyproject.toml         # Project metadata
└── README.md              # This file
```

### Key Components

- **AuthManager** (`acdown/auth.py`): Handles TOTP authentication, token storage, and configuration
- **Downloader** (`acdown/downloader.py`): Manages file analysis, chunked downloads, and concatenation
- **ProgressTracker** (`acdown/progress.py`): Beautiful progress display using Rich library
- **Logger** (`acdown/logger.py`): Configurable logging system
- **Utils** (`acdown/utils.py`): Helper functions for URL validation, size formatting, etc.
- **CLI** (`acdown/cli.py`): Typer-based command-line interface

## Security Considerations

1. **Token Storage**: Stored in binary format with restrictive permissions (600)
2. **TOTP Codes**: Never hardcoded; always provided at runtime
3. **Input Validation**: URLs validated before processing
4. **Path Sanitization**: Prevents directory traversal attacks
5. **No Plaintext Secrets**: All sensitive data in binary format

## API Compatibility

This client is designed to work with ACDown Server API endpoints:

- `POST /api/auth/login` - Authentication
- `POST /api/proxy/analyze` - File analysis
- `GET /api/proxy/part/:encryptedParams` - Chunk download
- `GET /health` - Health check

## Development

### Running from Source

```bash
# Using uv (recommended)
uv run acdown --help

# Or activate virtual environment first
source .venv/bin/activate
acdown --help
```

### Import as Package

```python
from acdown import AuthManager, Downloader, ProgressTracker
from acdown import validate_url, format_size

# Create instances
auth = AuthManager()
downloader = Downloader(config)
```

### Adding New Features

1. Add dependencies to `pyproject.toml`
2. Run `uv sync` to update lock file
3. Implement feature in appropriate module
4. Update this README if needed

## License

This project is open source. See LICENSE file for details.

## Support

For issues and feature requests, please visit the project repository.

---

**Happy Downloading! 🚀**
