# Timelapse for Prusa - Copilot Instructions

## Project Overview

This is a Python application that monitors Prusa 3D printers via the PrusaLink API, automatically captures timelapse images during printing using rpicam-still, creates MP4 videos with ffmpeg, and sends email notifications with the completed video.

**Key Features:**

- Automated timelapse capture during 3D prints
- PrusaLink API integration for printer status monitoring
- Optional Prusa Connect live camera streaming
- Email notifications with detailed print statistics
- Configurable capture intervals and video quality
- Camera rotation support (0, 90, 180, 270 degrees) for rotated camera mounts
- Security-hardened parameter sanitization

## Code Style Guidelines

### Python Conventions

- **Python Version:** Python 3.8+
- **Style Guide:** Follow PEP 8 conventions
- **Line Length:** Prefer 88-100 characters (Black formatter compatible)
- **Imports:** Organize as standard library, third-party, local (separated by blank lines)
- **Naming Conventions:**
  - Classes: `PascalCase` (e.g., `PrusaTimelapse`)
  - Functions/methods: `snake_case` (e.g., `capture_image`, `get_printer_status`)
  - Constants: `UPPER_SNAKE_CASE` (e.g., `API_TIMEOUT`)
  - Private methods: prefix with single underscore `_build_email_body`

### Code Organization

- **Class-Based:** Main functionality in `PrusaTimelapse` class
- **Single Responsibility:** Each method should have one clear purpose
- **Error Handling:** Always use try-except blocks with specific exceptions
- **Logging:** Use module-level logger (`logger = logging.getLogger(__name__)`)
- **Configuration:** All settings from environment variables via `.env` file

### Logging Standards

- **Levels:**
  - `logger.info()` - Normal operations, state changes, successful completions
  - `logger.warning()` - Recoverable errors, retries, fallback behaviors
  - `logger.error()` - Failures that prevent operation but allow continuation
  - `logger.debug()` - Detailed diagnostic information
- **Format:** `%(asctime)s - %(name)s - %(levelname)s - %(message)s`
- **Messages:** Clear, actionable, include relevant context (file paths, status codes, etc.)

### Security Requirements

**Critical:** Always sanitize user-provided input, especially shell parameters

- **Shell Command Safety:**

  - Use `shlex.split()` for parsing user-provided parameters
  - Check for dangerous characters: `;`, `&`, `|`, `` ` ``, `$()`, `${}`, `>`, `<`
  - Log and reject dangerous input with clear error messages
  - Never use `shell=True` in subprocess calls

- **File Operations:**

  - Validate file paths to prevent directory traversal
  - Use `Path` objects for path manipulation
  - Check file existence before operations

- **API Security:**
  - Store credentials in `.env` file (never in code)
  - Use environment variables for all sensitive data
  - Validate API responses before processing

## Documentation Style

### Docstrings

Use Google-style docstrings for all public functions, methods, and classes:

```python
def capture_image(self, output_path):
    """
    Capture a still image from the camera.

    Args:
        output_path (str): Path where the image will be saved

    Returns:
        bool: True if capture was successful, False otherwise

    Raises:
        ValueError: If output_path is invalid
    """
```

**Requirements:**

- All public functions and methods must have docstrings
- Include: brief description, Args, Returns, Raises (when applicable)
- Keep descriptions concise but complete
- Document complex logic with inline comments

### Code Comments

- **When to Comment:**

  - Complex algorithms or non-obvious logic
  - Workarounds for external API limitations
  - Security-critical sections
  - Configuration decisions

- **Comment Style:**
  - Use `#` for single-line comments
  - Place comments on the line above the code they describe
  - Keep comments updated with code changes

### README and Documentation

- Keep README.md up-to-date with setup instructions
- Document all environment variables with descriptions and examples
- Include troubleshooting section for common issues
- Provide examples for typical use cases

## Test Requirements

### Coverage Goals

- **Minimum Coverage:** 90% overall (MANDATORY)
- **Per-File Target:** 85%+ for all modules
- **Current Status:** 91% overall (101 tests passing)

**CRITICAL:** All new features MUST include comprehensive tests before code review. Coverage must remain at or above 90% overall. Pull requests that drop coverage below 90% will be rejected.

### Testing Framework

- **Framework:** pytest
- **Test Organization:**
  - `tests/conftest.py` - Shared fixtures
  - `tests/test_prusa_timelapse.py` - Main functionality tests
  - `tests/test_check_setup.py` - Setup verification tests

### Test Structure

**Test Classes:** Group related tests by functionality:

```python
class TestCaptureImage:
    """Test image capture functionality."""

    def test_capture_success(self, mock_env, tmp_path, monkeypatch):
        """Test successful image capture."""
        # Test implementation
```

**Naming Convention:**

- Test files: `test_*.py`
- Test classes: `Test*` (PascalCase)
- Test functions: `test_*` (snake_case, descriptive)

### Mocking Requirements

- **External Dependencies:** Always mock:

  - `subprocess.run` (camera/video commands)
  - `requests.get/put` (API calls)
  - `smtplib.SMTP` (email sending)
  - `os.path.exists` (file operations)
  - `shutil.rmtree` (directory removal)

- **Fixtures:** Use shared fixtures from `conftest.py`:
  - `mock_env` - Basic environment configuration
  - `mock_env_with_auth` - SMTP authentication enabled
  - `mock_env_with_prusa_connect` - Prusa Connect enabled
  - `mock_printer_status_*` - Various printer states

### Test Coverage Requirements

Every new feature or bug fix MUST include:

1. **Happy Path Test:** Test successful operation
2. **Error Path Tests:** Test failure scenarios:
   - Network errors (timeouts, connection failures)
   - File system errors (permissions, disk full)
   - Invalid input/configuration
   - Subprocess failures
3. **Edge Cases:** Test boundary conditions
4. **Integration:** Test interaction with other components

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=. --cov-report=term-missing --cov-report=html

# Run specific test
pytest tests/test_prusa_timelapse.py::TestClass::test_method

# Run in verbose mode
pytest -v
```

## Configuration Management

### Environment Variables

All configuration via `.env` file. Required variables:

- `PRUSA_PRINTER_HOST` - PrusaLink host URL (required)
- `PRUSA_API_KEY` - PrusaLink API key (required)
- `EMAIL_FROM` - Sender email address (required)
- `EMAIL_TO` - Recipient email address (required)
- `SMTP_SERVER` - SMTP server hostname (required)
- `SMTP_PORT` - SMTP server port (required)

**Validation:**

- Validate all required variables at startup
- Provide clear error messages for missing configuration
- Use sensible defaults for optional settings

## Dependencies and External Tools

### System Dependencies

- **rpicam-still:** Camera capture (Raspberry Pi camera)
- **ffmpeg:** Video encoding and creation
- **Python 3.8+:** Runtime environment

### Python Dependencies

Core (requirements.txt):

- `python-dotenv` - Environment variable management
- `requests` - HTTP client for API calls

Development (requirements-dev.txt):

- `pytest>=7.4.0` - Testing framework
- `pytest-cov>=4.1.0` - Coverage reporting
- `pytest-mock>=3.12.0` - Mocking utilities
- `responses>=0.24.0` - HTTP request mocking

## Error Handling Patterns

### API Calls

```python
try:
    response = requests.get(url, timeout=5)
    response.raise_for_status()
    return response.json()
except requests.exceptions.Timeout:
    logger.error("API request timed out")
    return None
except requests.exceptions.ConnectionError as e:
    logger.error(f"Connection error: {e}")
    return None
except requests.exceptions.RequestException as e:
    logger.error(f"API error: {e}")
    return None
```

### Subprocess Calls

```python
try:
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
    if result.returncode == 0:
        return True
    else:
        logger.error(f"Command failed: {result.stderr}")
        return False
except subprocess.TimeoutExpired:
    logger.error("Command timed out")
    return False
except Exception as e:
    logger.error(f"Unexpected error: {e}")
    return False
```

### File Operations

```python
try:
    with open(file_path, 'rb') as f:
        data = f.read()
    return data
except FileNotFoundError:
    logger.error(f"File not found: {file_path}")
    return None
except PermissionError:
    logger.error(f"Permission denied: {file_path}")
    return None
except Exception as e:
    logger.error(f"Error reading file: {e}")
    return None
```

## Architecture Patterns

### Main Monitoring Loop

- Poll printer status at regular intervals (`POLL_INTERVAL_SECONDS`)
- Detect print start/end by state changes
- Capture frames at configured intervals during printing
- Handle graceful shutdown (KeyboardInterrupt)

### State Management

- Track printing state with boolean flags
- Store print metadata (name, start time, job details)
- Maintain image sequence list during capture
- Reset state after print completion

### Video Creation Workflow

1. Capture images to timestamped directory in temp location
2. Create MP4 video using ffmpeg with frame sequence
3. Save video to prints directory
4. Send email notification with video attachment
5. Clean up: delete capture directory (images included in video)

## Common Pitfalls to Avoid

1. **Don't use `shell=True`** in subprocess calls (security risk)
2. **Don't hardcode paths** - use Path objects and configurable directories
3. **Don't ignore return codes** - always check subprocess/API results
4. **Don't mix string and Path types** - convert consistently
5. **Don't skip input validation** - sanitize all user-provided data
6. **Don't forget error logging** - every failure should be logged
7. **Don't block on I/O** - use timeouts for network and subprocess calls
8. **Don't leave resources open** - use context managers for files/connections

## Contribution Guidelines

When adding new features:

1. **Plan tests first:** Write test cases before implementation
2. **Maintain coverage:** Ensure new code has >90% test coverage (MANDATORY)
3. **Test all code paths:** Include happy path, error paths, edge cases, and integration tests
4. **Run coverage check:** Always verify coverage with `pytest --cov=. --cov-report=term`
5. **Document thoroughly:** Add docstrings and update README
6. **Follow patterns:** Use existing code structure as template
7. **Sanitize input:** Validate and sanitize all external input
8. **Log appropriately:** Add logging at info/warning/error levels
9. **Handle errors:** Include try-except blocks with specific exceptions
10. **Update .env.example:** Document new configuration variables

### Pre-Commit Checklist

Before committing any code:

- [ ] All tests pass (`pytest tests/`)
- [ ] Coverage is ≥90% (`pytest --cov=. --cov-report=term`)
- [ ] New features have comprehensive tests (happy path + error paths + edge cases)
- [ ] Docstrings added for all public functions/methods
- [ ] `.env.example` updated if new configuration added
- [ ] No security vulnerabilities introduced (shell injection, path traversal, etc.)
- [ ] Code follows PEP 8 style guidelines

**CRITICAL:** After making ANY changes to Python code, ALWAYS run `pytest tests/ --cov=. --cov-report=term -q` to verify:

1. All tests still pass (no regressions)
2. Coverage remains at or above 90%
3. New code has appropriate test coverage

If tests fail or coverage drops below 90%, fix the issues immediately before proceeding.

## Project-Specific Conventions

### File Naming

- Main script: `prusa_timelapse.py`
- Setup checker: `check_setup.py`
- Tests: `test_*.py`
- Temporary capture directories: `/tmp/timelapse_YYYYMMDD_HHMMSS/`
- Final videos: `{PRINTS_DIR}/YYYY-MM-DD-HH-MM_printname.mp4`
- Frame files: `frame_00000.jpg`, `frame_00001.jpg`, etc.

### Directory Structure

```bash
prusa-livestream/
├── prusa_timelapse.py    # Main monitoring script
├── check_setup.py         # Setup verification tool
├── .env                   # Configuration (not in git)
├── .env.example          # Configuration template
├── requirements.txt       # Production dependencies
├── requirements-dev.txt   # Development dependencies
├── tests/                # Test suite
│   ├── conftest.py       # Shared fixtures
│   ├── test_prusa_timelapse.py
│   └── test_check_setup.py
└── README.md             # Documentation
```

### Git Workflow

- Keep commits focused and atomic
- Write clear commit messages
- Don't commit `.env` file (contains secrets)
- Test before committing
- Update documentation with code changes
