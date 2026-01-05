# Test Suite

This directory contains the test suite for Timelapse for Prusa.

## Running Tests

Install test dependencies:

```bash
pip3 install -r requirements-dev.txt
```

Run all tests:

```bash
pytest
```

Run tests with coverage report:

```bash
pytest --cov=. --cov-report=term-missing
```

Run specific test file:

```bash
pytest tests/test_prusa_timelapse.py
pytest tests/test_check_setup.py
```

Run specific test:

```bash
pytest tests/test_prusa_timelapse.py::TestPrusaTimelapseInit::test_init_success
```

Generate HTML coverage report:

```bash
pytest --cov=. --cov-report=html
# Open htmlcov/index.html in browser
```

## Test Structure

- `conftest.py` - Shared fixtures and configuration
- `test_prusa_timelapse.py` - Tests for main timelapse monitoring script
- `test_check_setup.py` - Tests for setup verification script

## Test Coverage

Goal: >90% coverage for all modules

Current test categories:

- Initialization and configuration
- API communication
- Image capture
- Video creation
- Email sending
- Print workflow
- Error handling
- Security (parameter sanitization)

## Mocking

Tests use mocking extensively to avoid:

- Network requests to printer/Prusa Connect
- SMTP connections
- Camera hardware access
- File system operations
- Subprocess calls (rpicam-still, ffmpeg)

This allows tests to run quickly on any system without hardware dependencies.
