# ACDown Client Test Suite

Comprehensive pytest test suite for the ACDown Client project.

## Test Structure

```
tests/
├── __init__.py              # Test package initialization
├── conftest.py              # Shared fixtures and utilities
├── test_auth.py             # Authentication module tests
├── test_downloader.py       # Download engine tests
├── test_progress.py         # Progress tracking tests
├── test_utils.py            # Utility functions tests
├── test_cli.py              # CLI interface tests
└── test_integration.py      # Integration and workflow tests
```

## Test Coverage

### 1. Authentication Tests (`test_auth.py`)
- ✅ Initialization and default configuration
- ✅ Binary serialization/deserialization
- ✅ Data persistence (save/load)
- ✅ Login workflow (success/failure)
- ✅ Token validation
- ✅ Configuration management (set/get)
- ✅ Server URL configuration checks
- ✅ Logout functionality

**Total Tests:** ~35 tests

### 2. Downloader Tests (`test_downloader.py`)
- ✅ Downloader initialization
- ✅ File analysis
- ✅ Single part download (with retries)
- ✅ Concurrent part downloads
- ✅ Part concatenation
- ✅ Complete download workflow
- ✅ Error handling (disk space, network errors)

**Total Tests:** ~18 tests

### 3. Progress Tracker Tests (`test_progress.py`)
- ✅ Progress bar initialization
- ✅ Progress updates
- ✅ Speed calculation
- ✅ ETA calculation
- ✅ Size formatting
- ✅ Full download simulation

**Total Tests:** ~25 tests

### 4. Utility Functions Tests (`test_utils.py`)
- ✅ URL filename extraction
- ✅ URL validation
- ✅ Disk space checking
- ✅ Size formatting
- ✅ Duration formatting
- ✅ App data directory detection (cross-platform)

**Total Tests:** ~40 tests

### 5. CLI Interface Tests (`test_cli.py`)
- ✅ Download command (success/failure/options)
- ✅ Auth command (success/failure)
- ✅ Config command (set/get/validation)
- ✅ Logout command
- ✅ Help messages
- ✅ Error handling

**Total Tests:** ~25 tests

### 6. Integration Tests (`test_integration.py`)
- ✅ Complete authentication workflow
- ✅ Complete download workflow
- ✅ Configuration persistence
- ✅ Error recovery scenarios
- ✅ Concurrent downloads
- ✅ Data integrity verification

**Total Tests:** ~10 tests

**Grand Total:** ~153 tests

## Running Tests

### Install Test Dependencies

```bash
# Using uv (recommended)
uv pip install pytest pytest-asyncio pytest-cov

# Or using pip
pip install pytest pytest-asyncio pytest-cov
```

### Run All Tests

```bash
pytest
```

### Run Specific Test Files

```bash
# Authentication tests only
pytest tests/test_auth.py

# Downloader tests only
pytest tests/test_downloader.py

# CLI tests only
pytest tests/test_cli.py
```

### Run Specific Test Classes

```bash
# Run all auth initialization tests
pytest tests/test_auth.py::TestAuthManagerInit

# Run all downloader init tests
pytest tests/test_downloader.py::TestDownloaderInit
```

### Run Specific Test Functions

```bash
# Run a single test
pytest tests/test_auth.py::TestAuthManagerInit::test_init_creates_app_dir

# Run with verbose output
pytest tests/test_auth.py::TestAuthManagerInit::test_init_creates_app_dir -v
```

### Run with Markers

```bash
# Run only async tests
pytest -m asyncio

# Skip integration tests
pytest -m "not integration"

# Run only slow tests
pytest -m slow
```

### Run with Coverage

```bash
# Run tests with coverage report
pytest --cov=acdown --cov-report=term-missing

# Generate HTML coverage report
pytest --cov=acdown --cov-report=html

# Open HTML report
open htmlcov/index.html  # macOS
xdg-open htmlcov/index.html  # Linux
start htmlcov/index.html  # Windows
```

### Run with Detailed Output

```bash
# Verbose mode
pytest -v

# Show local variables on failure
pytest -l

# Show print statements
pytest -s

# Stop on first failure
pytest -x

# Maximum verbosity
pytest -vv
```

## Test Fixtures

The `conftest.py` file provides reusable fixtures:

- **`temp_dir`**: Temporary directory for test files (auto-cleanup)
- **`mock_auth_data`**: Mock authentication data dictionary
- **`mock_file_info`**: Mock file analysis response
- **`sample_binary_data`**: Pre-serialized binary data for auth tests
- **`event_loop`**: Async event loop for async tests
- **`mock_httpx_client`**: Mocked httpx.AsyncClient
- **`mock_console`**: Mocked Rich Console
- **`mock_progress_tracker`**: Mocked ProgressTracker

### Using Fixtures

```python
def test_example(temp_dir, mock_auth_data):
    """Example test using fixtures."""
    # temp_dir is automatically created and cleaned up
    test_file = temp_dir / "test.txt"
    test_file.write_text("content")
    
    # mock_auth_data provides consistent test data
    assert mock_auth_data['token'] == 'test_token_12345'
```

## Writing New Tests

### Test Structure

```python
import pytest
from unittest.mock import patch, MagicMock, AsyncMock

class TestYourModule:
    """Test suite for your module."""
    
    def test_basic_functionality(self):
        """Test basic feature."""
        # Arrange
        expected = "result"
        
        # Act
        actual = your_function()
        
        # Assert
        assert actual == expected
    
    @pytest.mark.asyncio
    async def test_async_functionality(self):
        """Test async feature."""
        # Mock async dependencies
        with patch('module.AsyncClass') as mock_class:
            mock_instance = AsyncMock()
            mock_instance.method.return_value = "result"
            mock_class.return_value = mock_instance
            
            # Call async function
            result = await your_async_function()
            
            assert result == "result"
```

### Best Practices

1. **Use descriptive test names**: `test_login_with_valid_totp_succeeds`
2. **Follow AAA pattern**: Arrange, Act, Assert
3. **Test one thing per test**: Keep tests focused
4. **Use fixtures**: Don't repeat setup code
5. **Mock external dependencies**: HTTP calls, file I/O, etc.
6. **Test edge cases**: Empty inputs, errors, boundaries
7. **Add docstrings**: Explain what and why

## Test Categories

### Unit Tests
- Test individual functions/methods in isolation
- Fast execution (< 1 second per test)
- No external dependencies
- Located in: `test_auth.py`, `test_downloader.py`, `test_progress.py`, `test_utils.py`

### Integration Tests
- Test complete workflows
- Multiple components working together
- Slower execution
- Located in: `test_integration.py`

### CLI Tests
- Test command-line interface
- Use Typer's CliRunner
- Test user interactions
- Located in: `test_cli.py`

## Continuous Integration

### GitHub Actions Example

```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.9", "3.10", "3.11", "3.12"]
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Set up Python ${{ matrix.python-version }}
      uses: actions/setup-python@v4
      with:
        python-version: ${{ matrix.python-version }}
    
    - name: Install dependencies
      run: |
        pip install pytest pytest-asyncio pytest-cov
        pip install -e .
    
    - name: Run tests with coverage
      run: |
        pytest --cov=acdown --cov-report=xml
    
    - name: Upload coverage to Codecov
      uses: codecov/codecov-action@v3
```

## Troubleshooting

### Common Issues

**Issue:** `ModuleNotFoundError: No module named 'acdown'`
```bash
# Install package in development mode
pip install -e .
```

**Issue:** Async tests not running
```bash
# Ensure pytest-asyncio is installed
pip install pytest-asyncio

# Check pytest.ini has asyncio_mode = "auto"
```

**Issue:** Tests failing due to network calls
```bash
# All external calls should be mocked
# Check that you're using patch() correctly
```

**Issue:** Fixture not found
```bash
# Ensure fixture is defined in conftest.py or imported
# Check fixture name spelling
```

### Debug Mode

```bash
# Drop into debugger on failure
pytest --pdb

# Print debug statements
pytest -s

# Show full traceback
pytest --tb=long
```

## Performance Tips

1. **Parallelize tests**: `pytest -n auto` (requires pytest-xdist)
2. **Skip slow tests**: `pytest -m "not slow"`
3. **Cache results**: `pytest --cache-clear`
4. **Profile tests**: `pytest --profile`

## Code Coverage Goals

- **Overall coverage**: ≥ 80%
- **Critical modules** (auth, downloader): ≥ 90%
- **Utility functions**: ≥ 85%
- **CLI interface**: ≥ 75%

Check current coverage:
```bash
pytest --cov=acdown --cov-report=term-missing
```

## Contributing

When adding new features:
1. Write tests first (TDD approach)
2. Ensure all existing tests pass
3. Maintain or improve coverage
4. Add integration tests for workflows
5. Update this README if needed

## Resources

- [pytest documentation](https://docs.pytest.org/)
- [pytest-asyncio documentation](https://pytest-asyncio.readthedocs.io/)
- [unittest.mock documentation](https://docs.python.org/3/library/unittest.mock.html)
- [Typer testing guide](https://typer.tiangolo.com/tutorial/testing/)
