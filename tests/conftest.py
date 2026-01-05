"""Pytest configuration and fixtures."""

import pytest


@pytest.fixture
def mock_env(monkeypatch, tmp_path):
    """Set up mock environment variables for testing."""
    env_vars = {
        "PRUSA_PRINTER_HOST": "192.168.1.12",
        "PRUSA_API_KEY": "test_api_key_12345",
        "CAPTURE_INTERVAL_SECONDS": "10",
        "IMAGE_WIDTH": "1280",
        "IMAGE_HEIGHT": "720",
        "CAMERA_ROTATION": "0",
        "FOCUS_DISTANCE": "22",
        "VIDEO_FPS": "10",
        "VIDEO_QUALITY": "28",
        "SMTP_SERVER": "192.168.1.10",
        "SMTP_PORT": "25",
        "SMTP_USERNAME": "",
        "SMTP_PASSWORD": "",
        "EMAIL_FROM": "utilities@example.com",
        "EMAIL_TO": "user@example.com",
        "POLL_INTERVAL_SECONDS": "10",
        "PRINTS_DIR_NAME": "prints",
        "RPICAM_EXTRA_PARAMS": "",
        "PRUSA_CONNECT_CAMERA_TOKEN": "",
        "PRUSA_CONNECT_CAMERA_FINGERPRINT": "",
    }

    for key, value in env_vars.items():
        monkeypatch.setenv(key, value)

    return env_vars


@pytest.fixture
def mock_env_with_auth(monkeypatch):
    """Set up mock environment with SMTP authentication."""
    env_vars = {
        "PRUSA_PRINTER_HOST": "192.168.1.12",
        "PRUSA_API_KEY": "test_api_key_12345",
        "CAPTURE_INTERVAL_SECONDS": "10",
        "IMAGE_WIDTH": "1280",
        "IMAGE_HEIGHT": "720",
        "CAMERA_ROTATION": "0",
        "FOCUS_DISTANCE": "22",
        "VIDEO_FPS": "10",
        "VIDEO_QUALITY": "28",
        "SMTP_SERVER": "smtp.gmail.com",
        "SMTP_PORT": "587",
        "SMTP_USERNAME": "user@gmail.com",
        "SMTP_PASSWORD": "app_password",
        "EMAIL_FROM": "user@gmail.com",
        "EMAIL_TO": "recipient@example.com",
        "POLL_INTERVAL_SECONDS": "10",
        "PRINTS_DIR_NAME": "prints",
        "RPICAM_EXTRA_PARAMS": "",
        "PRUSA_CONNECT_CAMERA_TOKEN": "",
        "PRUSA_CONNECT_CAMERA_FINGERPRINT": "",
    }

    for key, value in env_vars.items():
        monkeypatch.setenv(key, value)

    return env_vars


@pytest.fixture
def mock_env_with_prusa_connect(monkeypatch):
    """Set up mock environment with Prusa Connect enabled."""
    env_vars = {
        "PRUSA_PRINTER_HOST": "192.168.1.12",
        "PRUSA_API_KEY": "test_api_key_12345",
        "CAPTURE_INTERVAL_SECONDS": "10",
        "IMAGE_WIDTH": "1280",
        "IMAGE_HEIGHT": "720",
        "CAMERA_ROTATION": "0",
        "FOCUS_DISTANCE": "22",
        "VIDEO_FPS": "10",
        "VIDEO_QUALITY": "28",
        "SMTP_SERVER": "192.168.1.10",
        "SMTP_PORT": "25",
        "SMTP_USERNAME": "",
        "SMTP_PASSWORD": "",
        "EMAIL_FROM": "utilities@example.com",
        "EMAIL_TO": "user@example.com",
        "POLL_INTERVAL_SECONDS": "10",
        "PRINTS_DIR_NAME": "prints",
        "RPICAM_EXTRA_PARAMS": "",
        "PRUSA_CONNECT_CAMERA_TOKEN": "test_token_123",
        "PRUSA_CONNECT_CAMERA_FINGERPRINT": "test-fingerprint-uuid",
    }

    for key, value in env_vars.items():
        monkeypatch.setenv(key, value)

    return env_vars


@pytest.fixture
def mock_printer_status_idle():
    """Mock printer status response - IDLE state."""
    return {
        "printer": {
            "state": "IDLE",
            "temp_nozzle": 25.0,
            "target_nozzle": 0.0,
            "temp_bed": 24.0,
            "target_bed": 0.0,
            "axis_x": 0.0,
            "axis_y": 0.0,
            "axis_z": 0.0,
            "flow": 100,
            "speed": 100,
            "fan_hotend": 0,
            "fan_print": 0,
        },
        "job": None,
        "storage": {
            "path": "/usb/",
            "name": "USB",
            "read_only": False,
        },
    }


@pytest.fixture
def mock_printer_status_printing():
    """Mock printer status response - PRINTING state."""
    return {
        "printer": {
            "state": "PRINTING",
            "temp_nozzle": 215.0,
            "target_nozzle": 215.0,
            "temp_bed": 60.0,
            "target_bed": 60.0,
            "axis_x": 100.5,
            "axis_y": 120.3,
            "axis_z": 5.2,
            "flow": 100,
            "speed": 100,
            "fan_hotend": 5000,
            "fan_print": 3000,
        },
        "job": {
            "id": 1234,
            "state": "PRINTING",
            "progress": 45.5,
            "time_printing": 2700,
            "time_remaining": 3300,
            "file": {
                "name": "test_print.gcode",
                "display_name": "Test Print",
                "path": "/usb/test_print.gcode",
                "size": 1024000,
                "m_timestamp": 1704326400,
            },
        },
        "storage": {
            "path": "/usb/",
            "name": "USB",
            "read_only": False,
        },
    }


@pytest.fixture
def mock_printer_status_paused():
    """Mock printer status response - PAUSED state."""
    return {
        "printer": {
            "state": "PAUSED",
            "temp_nozzle": 215.0,
            "target_nozzle": 215.0,
            "temp_bed": 60.0,
            "target_bed": 60.0,
        },
        "job": {
            "state": "PAUSED",
            "progress": 30.0,
            "file": {
                "name": "test_print.gcode",
                "display_name": "Test Print",
            },
        },
    }


@pytest.fixture
def temp_test_dir(tmp_path):
    """Create a temporary test directory."""
    test_dir = tmp_path / "test_prints"
    test_dir.mkdir()
    return test_dir
