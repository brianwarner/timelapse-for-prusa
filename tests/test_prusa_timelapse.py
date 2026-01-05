"""Tests for prusa_timelapse.py"""

import pytest
import sys
import os
from unittest.mock import MagicMock, patch
from datetime import datetime
import requests


# Import the module to test
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from prusa_timelapse import PrusaTimelapse  # noqa: E402


class TestPrusaTimelapseInit:
    """Test PrusaTimelapse initialization."""

    def test_init_success(self, mock_env, tmp_path, monkeypatch):
        """Test successful initialization with valid config."""
        monkeypatch.setenv("HOME", str(tmp_path))

        with patch("prusa_timelapse.load_dotenv"):
            timelapse = PrusaTimelapse()

            assert timelapse.printer_host == "192.168.1.12"
            assert timelapse.api_key == "test_api_key_12345"
            assert timelapse.capture_interval == 10
            assert timelapse.image_width == 1280
            assert timelapse.image_height == 720
            assert timelapse.camera_rotation == 0
            assert timelapse.focus_distance == 22
            assert (
                timelapse.lens_position == 4.55
            )  # 100 / 22 = 4.545... rounded to 4.55
            assert timelapse.video_fps == 10
            assert timelapse.video_quality == 28
            assert timelapse.smtp_server == "192.168.1.10"
            assert timelapse.smtp_port == 25
            assert timelapse.email_to == "user@example.com"
            assert timelapse.poll_interval == 10
            assert not timelapse.is_printing
            assert timelapse.image_sequence == []

    def test_init_missing_printer_host(self, mock_env, monkeypatch):
        """Test initialization fails without printer host."""
        monkeypatch.delenv("PRUSA_PRINTER_HOST")

        with patch("prusa_timelapse.load_dotenv"):
            with pytest.raises(ValueError, match="PRUSA_PRINTER_HOST"):
                PrusaTimelapse()

    def test_init_missing_api_key(self, mock_env, monkeypatch):
        """Test initialization fails without API key."""
        monkeypatch.delenv("PRUSA_API_KEY")

        with patch("prusa_timelapse.load_dotenv"):
            with pytest.raises(ValueError, match="PRUSA_API_KEY"):
                PrusaTimelapse()

    def test_init_empty_prints_dir_name(self, mock_env, monkeypatch):
        """Test initialization fails with empty prints directory name."""
        monkeypatch.setenv("PRINTS_DIR_NAME", "")

        with patch("prusa_timelapse.load_dotenv"):
            with pytest.raises(ValueError, match="PRINTS_DIR_NAME cannot be empty"):
                PrusaTimelapse()

    def test_init_with_prusa_connect(
        self, mock_env_with_prusa_connect, tmp_path, monkeypatch
    ):
        """Test initialization with Prusa Connect enabled."""
        monkeypatch.setenv("HOME", str(tmp_path))

        with patch("prusa_timelapse.load_dotenv"):
            timelapse = PrusaTimelapse()

            assert timelapse.enable_prusa_connect_upload is True
            assert timelapse.prusa_connect_camera_token == "test_token_123"
            assert timelapse.prusa_connect_camera_fingerprint == "test-fingerprint-uuid"

    def test_init_mismatched_smtp_auth(self, mock_env, monkeypatch):
        """Test initialization fails with mismatched SMTP auth credentials."""
        monkeypatch.setenv("SMTP_USERNAME", "user@example.com")
        # SMTP_PASSWORD is empty in mock_env

        with patch("prusa_timelapse.load_dotenv"):
            with pytest.raises(ValueError, match="SMTP_USERNAME and SMTP_PASSWORD"):
                PrusaTimelapse()

    def test_init_without_email(self, mock_env, tmp_path, monkeypatch):
        """Test initialization succeeds without email configuration."""
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.delenv("EMAIL_TO")
        monkeypatch.delenv("SMTP_SERVER")

        with patch("prusa_timelapse.load_dotenv"):
            timelapse = PrusaTimelapse()

            assert timelapse.email_to is None
            assert timelapse.smtp_server is None
            assert timelapse.is_email_configured() is False

    def test_init_partial_email_config_no_server(self, mock_env, monkeypatch):
        """Test initialization fails with EMAIL_TO but no SMTP_SERVER."""
        monkeypatch.delenv("SMTP_SERVER")

        with patch("prusa_timelapse.load_dotenv"):
            with pytest.raises(ValueError, match="Email configuration incomplete"):
                PrusaTimelapse()

    def test_init_partial_email_config_no_recipient(self, mock_env, monkeypatch):
        """Test initialization fails with SMTP_SERVER but no EMAIL_TO."""
        monkeypatch.delenv("EMAIL_TO")

        with patch("prusa_timelapse.load_dotenv"):
            with pytest.raises(ValueError, match="Email configuration incomplete"):
                PrusaTimelapse()

    def test_init_invalid_focus_distance_low(
        self, mock_env, tmp_path, monkeypatch, caplog
    ):
        """Test initialization with invalid focus distance below range."""
        import logging

        caplog.set_level(logging.WARNING)
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.setenv("FOCUS_DISTANCE", "5")  # Below 10

        with patch("prusa_timelapse.load_dotenv"):
            timelapse = PrusaTimelapse()
            assert timelapse.focus_distance == 22  # Should default to 22
            assert "Invalid FOCUS_DISTANCE" in caplog.text

    def test_init_invalid_focus_distance_high(
        self, mock_env, tmp_path, monkeypatch, caplog
    ):
        """Test initialization with invalid focus distance above range."""
        import logging

        caplog.set_level(logging.WARNING)
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.setenv("FOCUS_DISTANCE", "150")  # Above 100

        with patch("prusa_timelapse.load_dotenv"):
            timelapse = PrusaTimelapse()
            assert timelapse.focus_distance == 22  # Should default to 22
            assert "Invalid FOCUS_DISTANCE" in caplog.text


class TestReloadEnvConfig:
    """Test runtime .env configuration reloading."""

    def test_reload_no_changes(self, mock_env, tmp_path, monkeypatch, caplog):
        """Test reload with no configuration changes."""
        monkeypatch.setenv("HOME", str(tmp_path))

        with patch("prusa_timelapse.load_dotenv"):
            timelapse = PrusaTimelapse()

            # Reload should succeed but report no changes
            result = timelapse.reload_env_config()

            assert result is True
            assert "Configuration reloaded with changes:" not in caplog.text

    def test_reload_capture_interval(self, mock_env, tmp_path, monkeypatch, caplog):
        """Test reloading capture interval."""
        import logging

        caplog.set_level(logging.INFO)
        monkeypatch.setenv("HOME", str(tmp_path))

        with patch("prusa_timelapse.load_dotenv") as mock_load:
            timelapse = PrusaTimelapse()
            assert timelapse.capture_interval == 10

            # Change environment variable
            monkeypatch.setenv("CAPTURE_INTERVAL_SECONDS", "20")

            # Reload configuration
            result = timelapse.reload_env_config()

            assert result is True
            assert timelapse.capture_interval == 20
            assert "CAPTURE_INTERVAL_SECONDS: 10s → 20s" in caplog.text
            assert mock_load.call_count == 2  # Once in __init__, once in reload

    def test_reload_poll_interval(self, mock_env, tmp_path, monkeypatch, caplog):
        """Test reloading poll interval."""
        import logging

        caplog.set_level(logging.INFO)
        monkeypatch.setenv("HOME", str(tmp_path))

        with patch("prusa_timelapse.load_dotenv"):
            timelapse = PrusaTimelapse()
            assert timelapse.poll_interval == 10

            monkeypatch.setenv("POLL_INTERVAL_SECONDS", "5")
            result = timelapse.reload_env_config()

            assert result is True
            assert timelapse.poll_interval == 5
            assert "POLL_INTERVAL_SECONDS: 10s → 5s" in caplog.text

    def test_reload_video_settings(self, mock_env, tmp_path, monkeypatch, caplog):
        """Test reloading video FPS and quality."""
        import logging

        caplog.set_level(logging.INFO)
        monkeypatch.setenv("HOME", str(tmp_path))

        with patch("prusa_timelapse.load_dotenv"):
            timelapse = PrusaTimelapse()
            assert timelapse.video_fps == 10
            assert timelapse.video_quality == 28

            monkeypatch.setenv("VIDEO_FPS", "30")
            monkeypatch.setenv("VIDEO_QUALITY", "23")
            result = timelapse.reload_env_config()

            assert result is True
            assert timelapse.video_fps == 30
            assert timelapse.video_quality == 23
            assert "VIDEO_FPS: 10 → 30" in caplog.text
            assert "VIDEO_QUALITY: 28 → 23" in caplog.text

    def test_reload_camera_rotation(self, mock_env, tmp_path, monkeypatch, caplog):
        """Test reloading camera rotation."""
        import logging

        caplog.set_level(logging.INFO)
        monkeypatch.setenv("HOME", str(tmp_path))

        with patch("prusa_timelapse.load_dotenv"):
            timelapse = PrusaTimelapse()
            assert timelapse.camera_rotation == 0

            monkeypatch.setenv("CAMERA_ROTATION", "90")
            result = timelapse.reload_env_config()

            assert result is True
            assert timelapse.camera_rotation == 90
            assert "CAMERA_ROTATION: 0° → 90°" in caplog.text

    def test_reload_rpicam_params(self, mock_env, tmp_path, monkeypatch, caplog):
        """Test reloading camera extra parameters."""
        import logging

        caplog.set_level(logging.INFO)
        monkeypatch.setenv("HOME", str(tmp_path))

        with patch("prusa_timelapse.load_dotenv"):
            timelapse = PrusaTimelapse()
            assert timelapse.rpicam_extra_params == ""

            monkeypatch.setenv("RPICAM_EXTRA_PARAMS", "--shutter 100000")
            result = timelapse.reload_env_config()

            assert result is True
            assert timelapse.rpicam_extra_params == "--shutter 100000"
            assert "RPICAM_EXTRA_PARAMS: '' → '--shutter 100000'" in caplog.text

    def test_reload_multiple_changes(self, mock_env, tmp_path, monkeypatch, caplog):
        """Test reloading multiple configuration values at once."""
        import logging

        caplog.set_level(logging.INFO)
        monkeypatch.setenv("HOME", str(tmp_path))

        with patch("prusa_timelapse.load_dotenv"):
            timelapse = PrusaTimelapse()

            # Change multiple values
            monkeypatch.setenv("CAPTURE_INTERVAL_SECONDS", "15")
            monkeypatch.setenv("VIDEO_FPS", "24")
            monkeypatch.setenv("CAMERA_ROTATION", "180")

            result = timelapse.reload_env_config()

            assert result is True
            assert timelapse.capture_interval == 15
            assert timelapse.video_fps == 24
            assert timelapse.camera_rotation == 180
            assert "CAPTURE_INTERVAL_SECONDS: 10s → 15s" in caplog.text
            assert "VIDEO_FPS: 10 → 24" in caplog.text
            assert "CAMERA_ROTATION: 0° → 180°" in caplog.text

    def test_reload_focus_distance(self, mock_env, tmp_path, monkeypatch, caplog):
        """Test reloading focus distance."""
        import logging

        caplog.set_level(logging.INFO)
        monkeypatch.setenv("HOME", str(tmp_path))

        with patch("prusa_timelapse.load_dotenv"):
            timelapse = PrusaTimelapse()
            assert timelapse.focus_distance == 22
            assert timelapse.lens_position == 4.55  # 100 / 22

            monkeypatch.setenv("FOCUS_DISTANCE", "50")
            result = timelapse.reload_env_config()

            assert result is True
            assert timelapse.focus_distance == 50
            assert timelapse.lens_position == 2.0  # 100 / 50
            assert "FOCUS_DISTANCE: 22cm → 50cm" in caplog.text
            assert "lens position: 4.55 → 2.0" in caplog.text

    def test_reload_invalid_rotation(self, mock_env, tmp_path, monkeypatch, caplog):
        """Test reload fails gracefully with invalid rotation."""
        import logging

        caplog.set_level(logging.WARNING)
        monkeypatch.setenv("HOME", str(tmp_path))

        with patch("prusa_timelapse.load_dotenv"):
            timelapse = PrusaTimelapse()
            timelapse.camera_rotation

            # Set invalid rotation value
            monkeypatch.setenv("CAMERA_ROTATION", "45")

            result = timelapse.reload_env_config()

            # Reload succeeds, but rotation defaults to 0
            assert result is True
            assert timelapse.camera_rotation == 0  # Invalid values default to 0
            assert "Invalid rotation" in caplog.text

    def test_reload_dangerous_params(self, mock_env, tmp_path, monkeypatch, caplog):
        """Test reload rejects dangerous camera parameters."""
        import logging

        caplog.set_level(logging.WARNING)
        monkeypatch.setenv("HOME", str(tmp_path))

        with patch("prusa_timelapse.load_dotenv"):
            timelapse = PrusaTimelapse()

            # Try to set dangerous parameters
            monkeypatch.setenv("RPICAM_EXTRA_PARAMS", "--shutter 100000; rm -rf /")

            result = timelapse.reload_env_config()

            # Should fail due to dangerous characters
            assert result is False
            assert timelapse.rpicam_extra_params == ""
            assert "Failed to reload configuration" in caplog.text


class TestSanitizeRpicamParams:
    """Test rpicam parameter sanitization."""

    def test_sanitize_empty_params(self, mock_env, tmp_path, monkeypatch):
        """Test empty parameters are accepted."""
        monkeypatch.setenv("HOME", str(tmp_path))

        with patch("prusa_timelapse.load_dotenv"):
            timelapse = PrusaTimelapse()
            assert timelapse.rpicam_extra_params == ""

    def test_sanitize_valid_params(self, mock_env, tmp_path, monkeypatch):
        """Test valid parameters are accepted."""
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.setenv("RPICAM_EXTRA_PARAMS", "--shutter 100000 --awb auto")

        with patch("prusa_timelapse.load_dotenv"):
            timelapse = PrusaTimelapse()
            assert timelapse.rpicam_extra_params == "--shutter 100000 --awb auto"

    def test_sanitize_dangerous_ampersand(self, mock_env, monkeypatch):
        """Test dangerous && pattern is rejected."""
        monkeypatch.setenv("RPICAM_EXTRA_PARAMS", "--shutter 100000 && rm -rf /")

        with patch("prusa_timelapse.load_dotenv"):
            with pytest.raises(ValueError, match="Dangerous pattern '&&'"):
                PrusaTimelapse()

    def test_sanitize_dangerous_semicolon(self, mock_env, monkeypatch):
        """Test dangerous ; pattern is rejected."""
        monkeypatch.setenv("RPICAM_EXTRA_PARAMS", "--shutter 100000; echo hack")

        with patch("prusa_timelapse.load_dotenv"):
            with pytest.raises(ValueError, match="Dangerous pattern ';'"):
                PrusaTimelapse()

    def test_sanitize_dangerous_pipe(self, mock_env, monkeypatch):
        """Test dangerous || pattern is rejected."""
        monkeypatch.setenv("RPICAM_EXTRA_PARAMS", "--awb auto || cat /etc/passwd")

        with patch("prusa_timelapse.load_dotenv"):
            with pytest.raises(ValueError, match="Dangerous pattern '\\|\\|'"):
                PrusaTimelapse()

    def test_sanitize_dangerous_backtick(self, mock_env, monkeypatch):
        """Test dangerous backtick is rejected."""
        monkeypatch.setenv("RPICAM_EXTRA_PARAMS", "`whoami`")

        with patch("prusa_timelapse.load_dotenv"):
            with pytest.raises(ValueError, match="Dangerous pattern '`'"):
                PrusaTimelapse()

    def test_sanitize_dangerous_command_substitution(self, mock_env, monkeypatch):
        """Test dangerous $( pattern is rejected."""
        monkeypatch.setenv("RPICAM_EXTRA_PARAMS", "$(whoami)")

        with patch("prusa_timelapse.load_dotenv"):
            with pytest.raises(ValueError, match="Dangerous pattern '\\$\\('"):
                PrusaTimelapse()


class TestCameraRotation:
    """Test camera rotation configuration and functionality."""

    def test_rotation_default_zero(self, mock_env, tmp_path, monkeypatch):
        """Test default rotation is 0 degrees."""
        monkeypatch.setenv("HOME", str(tmp_path))

        with patch("prusa_timelapse.load_dotenv"):
            timelapse = PrusaTimelapse()
            assert timelapse.camera_rotation == 0

    def test_rotation_90_degrees(self, mock_env, tmp_path, monkeypatch):
        """Test 90 degree rotation is accepted."""
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.setenv("CAMERA_ROTATION", "90")

        with patch("prusa_timelapse.load_dotenv"):
            timelapse = PrusaTimelapse()
            assert timelapse.camera_rotation == 90

    def test_rotation_180_degrees(self, mock_env, tmp_path, monkeypatch):
        """Test 180 degree rotation is accepted."""
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.setenv("CAMERA_ROTATION", "180")

        with patch("prusa_timelapse.load_dotenv"):
            timelapse = PrusaTimelapse()
            assert timelapse.camera_rotation == 180

    def test_rotation_270_degrees(self, mock_env, tmp_path, monkeypatch):
        """Test 270 degree rotation is accepted."""
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.setenv("CAMERA_ROTATION", "270")

        with patch("prusa_timelapse.load_dotenv"):
            timelapse = PrusaTimelapse()
            assert timelapse.camera_rotation == 270

    def test_rotation_invalid_value(self, mock_env, tmp_path, monkeypatch):
        """Test invalid rotation value defaults to 0."""
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.setenv("CAMERA_ROTATION", "45")

        with patch("prusa_timelapse.load_dotenv"):
            timelapse = PrusaTimelapse()
            assert timelapse.camera_rotation == 0

    def test_rotation_invalid_string(self, mock_env, tmp_path, monkeypatch):
        """Test invalid rotation string defaults to 0."""
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.setenv("CAMERA_ROTATION", "invalid")

        with patch("prusa_timelapse.load_dotenv"):
            timelapse = PrusaTimelapse()
            assert timelapse.camera_rotation == 0

    def test_upload_with_90_rotation(self, mock_env, tmp_path, monkeypatch):
        """Test Prusa Connect upload with 90 degree rotation."""
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.setenv("CAMERA_ROTATION", "90")
        monkeypatch.setenv("PRUSA_CONNECT_CAMERA_TOKEN", "test_token")
        monkeypatch.setenv("PRUSA_CONNECT_CAMERA_FINGERPRINT", "test_fingerprint")

        test_image = tmp_path / "test.jpg"
        test_image.write_bytes(b"fake image data")

        with patch("prusa_timelapse.load_dotenv"):
            timelapse = PrusaTimelapse()

            with patch(
                "prusa_lib.upload_to_prusa_connect", return_value=True
            ) as mock_upload:
                result = timelapse.upload_to_prusa_connect(str(test_image))

                assert result is True
                mock_upload.assert_called_once_with(
                    str(test_image), "test_token", "test_fingerprint", rotation=90
                )

    def test_video_with_90_rotation(self, mock_env, tmp_path, monkeypatch):
        """Test video creation with 90 degree rotation filter."""
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.setenv("CAMERA_ROTATION", "90")

        with patch("prusa_timelapse.load_dotenv"):
            timelapse = PrusaTimelapse()

            image_dir = tmp_path / "test_images"
            image_dir.mkdir()
            # Create dummy frame files
            for i in range(10):
                (image_dir / f"frame_{i:05d}.jpg").write_bytes(b"fake jpg")

            with patch("subprocess.run") as mock_run:
                with patch("os.path.exists", return_value=True):
                    with patch("os.path.getsize", return_value=1024 * 1024):
                        mock_result = MagicMock()
                        mock_result.returncode = 0
                        mock_result.stderr = ""
                        mock_run.return_value = mock_result

                        result = timelapse.create_video(image_dir, "/tmp/output.mp4")

                        assert result is True
                        call_args = mock_run.call_args[0][0]
                        # Check for transpose filter
                        assert "-vf" in call_args
                        vf_index = call_args.index("-vf")
                        assert "transpose=1" in call_args[vf_index + 1]

    def test_video_with_180_rotation(self, mock_env, tmp_path, monkeypatch):
        """Test video creation with 180 degree rotation filter."""
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.setenv("CAMERA_ROTATION", "180")

        with patch("prusa_timelapse.load_dotenv"):
            timelapse = PrusaTimelapse()

            image_dir = tmp_path / "test_images"
            image_dir.mkdir()
            # Create dummy frame files
            for i in range(10):
                (image_dir / f"frame_{i:05d}.jpg").write_bytes(b"fake jpg")

            with patch("subprocess.run") as mock_run:
                with patch("os.path.exists", return_value=True):
                    with patch("os.path.getsize", return_value=1024 * 1024):
                        mock_result = MagicMock()
                        mock_result.returncode = 0
                        mock_result.stderr = ""
                        mock_run.return_value = mock_result

                        result = timelapse.create_video(image_dir, "/tmp/output.mp4")

                        assert result is True
                        call_args = mock_run.call_args[0][0]
                        # Check for double transpose filter
                        assert "-vf" in call_args
                        vf_index = call_args.index("-vf")
                        assert "transpose=1,transpose=1" in call_args[vf_index + 1]

    def test_video_with_270_rotation(self, mock_env, tmp_path, monkeypatch):
        """Test video creation with 270 degree rotation filter."""
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.setenv("CAMERA_ROTATION", "270")

        with patch("prusa_timelapse.load_dotenv"):
            timelapse = PrusaTimelapse()

            image_dir = tmp_path / "test_images"
            image_dir.mkdir()
            # Create dummy frame files
            for i in range(10):
                (image_dir / f"frame_{i:05d}.jpg").write_bytes(b"fake jpg")

            with patch("subprocess.run") as mock_run:
                with patch("os.path.exists", return_value=True):
                    with patch("os.path.getsize", return_value=1024 * 1024):
                        mock_result = MagicMock()
                        mock_result.returncode = 0
                        mock_result.stderr = ""
                        mock_run.return_value = mock_result

                        result = timelapse.create_video(image_dir, "/tmp/output.mp4")

                        assert result is True
                        call_args = mock_run.call_args[0][0]
                        # Check for transpose=2 filter
                        assert "-vf" in call_args
                        vf_index = call_args.index("-vf")
                        assert "transpose=2" in call_args[vf_index + 1]


class TestGetPrinterStatus:
    """Test printer status retrieval."""

    def test_get_status_success(
        self, mock_env, tmp_path, monkeypatch, mock_printer_status_idle
    ):
        """Test successful status retrieval."""
        monkeypatch.setenv("HOME", str(tmp_path))

        with patch("prusa_timelapse.load_dotenv"):
            timelapse = PrusaTimelapse()

            with patch("requests.get") as mock_get:
                mock_response = MagicMock()
                mock_response.status_code = 200
                mock_response.json.return_value = mock_printer_status_idle
                mock_get.return_value = mock_response

                status = timelapse.get_printer_status()

                assert status == mock_printer_status_idle
                assert timelapse.connection_errors == 0
                mock_get.assert_called_once()

    def test_get_status_timeout(self, mock_env, tmp_path, monkeypatch):
        """Test status retrieval with timeout."""
        monkeypatch.setenv("HOME", str(tmp_path))

        with patch("prusa_timelapse.load_dotenv"):
            timelapse = PrusaTimelapse()

            with patch("requests.get") as mock_get:
                mock_get.side_effect = requests.exceptions.Timeout()

                status = timelapse.get_printer_status()

                assert status is None
                assert timelapse.connection_errors == 1

    def test_get_status_connection_error(self, mock_env, tmp_path, monkeypatch):
        """Test status retrieval with connection error."""
        monkeypatch.setenv("HOME", str(tmp_path))

        with patch("prusa_timelapse.load_dotenv"):
            timelapse = PrusaTimelapse()

            with patch("requests.get") as mock_get:
                mock_get.side_effect = requests.exceptions.ConnectionError()

                status = timelapse.get_printer_status()

                assert status is None
                assert timelapse.connection_errors == 1

    def test_get_status_http_error(self, mock_env, tmp_path, monkeypatch):
        """Test status retrieval with HTTP error."""
        monkeypatch.setenv("HOME", str(tmp_path))

        with patch("prusa_timelapse.load_dotenv"):
            timelapse = PrusaTimelapse()

            with patch("prusa_lib.get_printer_status", return_value=None):
                status = timelapse.get_printer_status()

                assert status is None
                # Error counter should increment
                assert timelapse.connection_errors == 1


class TestPrinterState:
    """Test printer state detection."""

    def test_is_printing_idle(
        self, mock_env, tmp_path, monkeypatch, mock_printer_status_idle
    ):
        """Test printer is not printing when IDLE."""
        monkeypatch.setenv("HOME", str(tmp_path))

        with patch("prusa_timelapse.load_dotenv"):
            timelapse = PrusaTimelapse()

            assert timelapse.is_printer_printing(mock_printer_status_idle) is False

    def test_is_printing_active(
        self, mock_env, tmp_path, monkeypatch, mock_printer_status_printing
    ):
        """Test printer is printing when PRINTING."""
        monkeypatch.setenv("HOME", str(tmp_path))

        with patch("prusa_timelapse.load_dotenv"):
            timelapse = PrusaTimelapse()

            assert timelapse.is_printer_printing(mock_printer_status_printing) is True

    def test_is_printing_paused(
        self, mock_env, tmp_path, monkeypatch, mock_printer_status_paused
    ):
        """Test printer is printing when PAUSED."""
        monkeypatch.setenv("HOME", str(tmp_path))

        with patch("prusa_timelapse.load_dotenv"):
            timelapse = PrusaTimelapse()

            assert timelapse.is_printer_printing(mock_printer_status_paused) is True

    def test_is_printing_no_status(self, mock_env, tmp_path, monkeypatch):
        """Test printer is not printing with no status."""
        monkeypatch.setenv("HOME", str(tmp_path))

        with patch("prusa_timelapse.load_dotenv"):
            timelapse = PrusaTimelapse()

            assert timelapse.is_printer_printing(None) is False

    def test_get_job_name(
        self, mock_env, tmp_path, monkeypatch, mock_printer_status_printing
    ):
        """Test job name extraction."""
        monkeypatch.setenv("HOME", str(tmp_path))

        with patch("prusa_timelapse.load_dotenv"):
            timelapse = PrusaTimelapse()

            # Extract job info from status (get_job_name now expects job info structure)
            job_info = mock_printer_status_printing["job"]
            name = timelapse.get_job_name(job_info)
            assert name == "Test Print"

    def test_get_job_name_no_job(
        self, mock_env, tmp_path, monkeypatch, mock_printer_status_idle
    ):
        """Test job name when no job active."""
        monkeypatch.setenv("HOME", str(tmp_path))

        with patch("prusa_timelapse.load_dotenv"):
            timelapse = PrusaTimelapse()

            # Pass None to simulate no job info available
            name = timelapse.get_job_name(None)
            assert name == "unknown"


class TestCaptureImage:
    """Test image capture functionality."""

    def test_capture_success(self, mock_env, tmp_path, monkeypatch):
        """Test successful image capture."""
        monkeypatch.setenv("HOME", str(tmp_path))

        with patch("prusa_timelapse.load_dotenv"):
            timelapse = PrusaTimelapse()

            with patch("subprocess.run") as mock_run:
                with patch("os.path.exists", return_value=True):
                    mock_result = MagicMock()
                    mock_result.returncode = 0
                    mock_result.stderr = ""
                    mock_run.return_value = mock_result

                    result = timelapse.capture_image("/tmp/test.jpg")

                    assert result is True
                    mock_run.assert_called_once()
                    # Check that rpicam-still was called with correct params
                    call_args = mock_run.call_args[0][0]
                    assert "rpicam-still" == call_args[0]
                    assert "--output" in call_args
                    assert "/tmp/test.jpg" in call_args
                    assert "--width" in call_args

    def test_capture_with_extra_params(self, mock_env, tmp_path, monkeypatch):
        """Test image capture with extra parameters."""
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.setenv("RPICAM_EXTRA_PARAMS", "--shutter 100000 --awb auto")

        with patch("prusa_timelapse.load_dotenv"):
            timelapse = PrusaTimelapse()

            with patch("subprocess.run") as mock_run:
                with patch("os.path.exists", return_value=True):
                    mock_result = MagicMock()
                    mock_result.returncode = 0
                    mock_result.stderr = ""
                    mock_run.return_value = mock_result

                    result = timelapse.capture_image("/tmp/test.jpg")

                    assert result is True
                    call_args = mock_run.call_args[0][0]
                    assert "--shutter" in call_args
                    assert "--awb" in call_args

    def test_capture_failure(self, mock_env, tmp_path, monkeypatch):
        """Test image capture failure."""
        monkeypatch.setenv("HOME", str(tmp_path))

        with patch("prusa_timelapse.load_dotenv"):
            timelapse = PrusaTimelapse()

            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(returncode=1)

                result = timelapse.capture_image("/tmp/test.jpg")

                assert result is False

    def test_capture_timeout(self, mock_env, tmp_path, monkeypatch):
        """Test image capture timeout."""
        monkeypatch.setenv("HOME", str(tmp_path))

        with patch("prusa_timelapse.load_dotenv"):
            timelapse = PrusaTimelapse()

            with patch("subprocess.run") as mock_run:
                import subprocess

                mock_run.side_effect = subprocess.TimeoutExpired("rpicam-still", 20)

                result = timelapse.capture_image("/tmp/test.jpg")

                assert result is False

    def test_capture_generic_error(self, mock_env, tmp_path, monkeypatch):
        """Test image capture with generic error."""
        monkeypatch.setenv("HOME", str(tmp_path))

        with patch("prusa_timelapse.load_dotenv"):
            timelapse = PrusaTimelapse()

            with patch("subprocess.run") as mock_run:
                mock_run.side_effect = Exception("Camera error")

                result = timelapse.capture_image("/tmp/test.jpg")

                assert result is False


class TestCreateVideo:
    """Test video creation functionality."""

    def test_create_video_success(self, mock_env, tmp_path, monkeypatch):
        """Test successful video creation."""
        monkeypatch.setenv("HOME", str(tmp_path))

        with patch("prusa_timelapse.load_dotenv"):
            timelapse = PrusaTimelapse()

            # Create test image directory
            image_dir = tmp_path / "test_images"
            image_dir.mkdir()
            # Create dummy frame files
            for i in range(10):
                (image_dir / f"frame_{i:05d}.jpg").write_bytes(b"fake jpg")

            with patch("subprocess.run") as mock_run:
                with patch("os.path.exists", return_value=True):
                    with patch("os.path.getsize", return_value=1024 * 1024):
                        mock_result = MagicMock()
                        mock_result.returncode = 0
                        mock_result.stderr = ""
                        mock_run.return_value = mock_result

                        result = timelapse.create_video(image_dir, "/tmp/output.mp4")

                        assert result is True
                        mock_run.assert_called_once()
                        call_args = mock_run.call_args[0][0]
                        assert "ffmpeg" == call_args[0]
                        assert "-framerate" in call_args

    def test_create_video_failure(self, mock_env, tmp_path, monkeypatch):
        """Test video creation failure."""
        monkeypatch.setenv("HOME", str(tmp_path))

        with patch("prusa_timelapse.load_dotenv"):
            timelapse = PrusaTimelapse()

            image_dir = tmp_path / "test_images"
            image_dir.mkdir()

            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(returncode=1)

                result = timelapse.create_video(image_dir, "/tmp/output.mp4")

                assert result is False

    def test_create_video_timeout(self, mock_env, tmp_path, monkeypatch):
        """Test video creation timeout."""
        monkeypatch.setenv("HOME", str(tmp_path))

        with patch("prusa_timelapse.load_dotenv"):
            timelapse = PrusaTimelapse()

            image_dir = tmp_path / "test_images"
            image_dir.mkdir()

            with patch("subprocess.run") as mock_run:
                import subprocess

                mock_run.side_effect = subprocess.TimeoutExpired("ffmpeg", 300)

                result = timelapse.create_video(image_dir, "/tmp/output.mp4")

                assert result is False

    def test_create_video_generic_error(self, mock_env, tmp_path, monkeypatch):
        """Test video creation with generic error."""
        monkeypatch.setenv("HOME", str(tmp_path))

        with patch("prusa_timelapse.load_dotenv"):
            timelapse = PrusaTimelapse()

            image_dir = tmp_path / "test_images"
            image_dir.mkdir()

            with patch("subprocess.run") as mock_run:
                mock_run.side_effect = Exception("Encoding error")

                result = timelapse.create_video(image_dir, "/tmp/output.mp4")

                assert result is False


class TestPrusaConnect:
    """Test Prusa Connect upload functionality."""

    def test_upload_disabled(self, mock_env, tmp_path, monkeypatch):
        """Test upload skipped when Prusa Connect disabled."""
        monkeypatch.setenv("HOME", str(tmp_path))

        with patch("prusa_timelapse.load_dotenv"):
            timelapse = PrusaTimelapse()

            result = timelapse.upload_to_prusa_connect("/tmp/test.jpg")

            assert result is True  # Returns True when disabled

    def test_upload_success(self, mock_env_with_prusa_connect, tmp_path, monkeypatch):
        """Test successful Prusa Connect upload."""
        monkeypatch.setenv("HOME", str(tmp_path))

        test_image = tmp_path / "test.jpg"
        test_image.write_bytes(b"fake image data")

        with patch("prusa_timelapse.load_dotenv"):
            timelapse = PrusaTimelapse()

            with patch("requests.put") as mock_put:
                mock_response = MagicMock()
                mock_response.status_code = 204
                mock_put.return_value = mock_response

                result = timelapse.upload_to_prusa_connect(str(test_image))

                assert result is True
                mock_put.assert_called_once()
                # Check headers
                call_kwargs = mock_put.call_args[1]
                assert "Fingerprint" in call_kwargs["headers"]
                assert "Token" in call_kwargs["headers"]

    def test_upload_http_200(self, mock_env_with_prusa_connect, tmp_path, monkeypatch):
        """Test Prusa Connect upload with HTTP 200 response."""
        monkeypatch.setenv("HOME", str(tmp_path))

        test_image = tmp_path / "test.jpg"
        test_image.write_bytes(b"fake image data")

        with patch("prusa_timelapse.load_dotenv"):
            timelapse = PrusaTimelapse()

            with patch("requests.put") as mock_put:
                mock_response = MagicMock()
                mock_response.status_code = 200
                mock_put.return_value = mock_response

                result = timelapse.upload_to_prusa_connect(str(test_image))

                assert result is True

    def test_upload_failure(self, mock_env_with_prusa_connect, tmp_path, monkeypatch):
        """Test Prusa Connect upload failure."""
        monkeypatch.setenv("HOME", str(tmp_path))

        test_image = tmp_path / "test.jpg"
        test_image.write_bytes(b"fake image data")

        with patch("prusa_timelapse.load_dotenv"):
            timelapse = PrusaTimelapse()

            with patch("requests.put") as mock_put:
                mock_response = MagicMock()
                mock_response.status_code = 401
                mock_put.return_value = mock_response

                result = timelapse.upload_to_prusa_connect(str(test_image))

                assert result is False

    def test_upload_exception(self, mock_env_with_prusa_connect, tmp_path, monkeypatch):
        """Test Prusa Connect upload with exception."""
        monkeypatch.setenv("HOME", str(tmp_path))

        test_image = tmp_path / "test.jpg"
        test_image.write_bytes(b"fake image data")

        with patch("prusa_timelapse.load_dotenv"):
            timelapse = PrusaTimelapse()

            with patch("requests.put") as mock_put:
                mock_put.side_effect = Exception("Network error")

                result = timelapse.upload_to_prusa_connect(str(test_image))

                assert result is False

    def test_upload_file_read_error(
        self, mock_env_with_prusa_connect, tmp_path, monkeypatch
    ):
        """Test Prusa Connect upload with file read error."""
        monkeypatch.setenv("HOME", str(tmp_path))

        with patch("prusa_timelapse.load_dotenv"):
            timelapse = PrusaTimelapse()

            # Try to upload non-existent file
            result = timelapse.upload_to_prusa_connect("/nonexistent/file.jpg")

            assert result is False


class TestEmailFunctionality:
    """Test email sending functionality."""

    def test_send_email_success(self, mock_env, tmp_path, monkeypatch):
        """Test successful email sending."""
        monkeypatch.setenv("HOME", str(tmp_path))

        video_file = tmp_path / "test.mp4"
        video_file.write_bytes(b"fake video")

        with patch("prusa_timelapse.load_dotenv"):
            timelapse = PrusaTimelapse()
            timelapse.current_print_start = datetime.now()

            with patch("smtplib.SMTP") as mock_smtp:
                mock_server = MagicMock()
                mock_smtp.return_value.__enter__.return_value = mock_server

                timelapse.send_email(str(video_file), "TestPrint", 3600)

                mock_server.send_message.assert_called_once()
                assert mock_server.send_message.called

    def test_send_email_with_auth(self, mock_env_with_auth, tmp_path, monkeypatch):
        """Test email sending with SMTP authentication."""
        monkeypatch.setenv("HOME", str(tmp_path))

        video_file = tmp_path / "test.mp4"
        video_file.write_bytes(b"fake video")

        with patch("prusa_timelapse.load_dotenv"):
            timelapse = PrusaTimelapse()
            timelapse.current_print_start = datetime.now()

            with patch("smtplib.SMTP") as mock_smtp:
                mock_server = MagicMock()
                mock_smtp.return_value.__enter__.return_value = mock_server

                timelapse.send_email(str(video_file), "TestPrint", 3600)

                assert mock_server.starttls.called
                assert mock_server.login.called

    def test_send_email_failure(self, mock_env, tmp_path, monkeypatch):
        """Test email sending failure."""
        monkeypatch.setenv("HOME", str(tmp_path))

        video_file = tmp_path / "test.mp4"
        video_file.write_bytes(b"fake video")

        with patch("prusa_timelapse.load_dotenv"):
            timelapse = PrusaTimelapse()
            timelapse.current_print_start = datetime.now()

            with patch("smtplib.SMTP") as mock_smtp:
                mock_smtp.side_effect = Exception("SMTP error")

                # send_email doesn't return anything, just logs the error
                timelapse.send_email(str(video_file), "TestPrint", 3600)

    def test_send_email_not_configured(self, mock_env, tmp_path, monkeypatch, caplog):
        """Test that send_email returns early when email is not configured."""
        import logging

        caplog.set_level(logging.INFO)

        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.delenv("EMAIL_TO")
        monkeypatch.delenv("SMTP_SERVER")

        video_file = tmp_path / "test.mp4"
        video_file.write_bytes(b"fake video")

        with patch("prusa_timelapse.load_dotenv"):
            timelapse = PrusaTimelapse()
            timelapse.current_print_start = datetime.now()

            with patch("smtplib.SMTP") as mock_smtp:
                timelapse.send_email(str(video_file), "TestPrint", 3600)

                # SMTP should not be called at all
                mock_smtp.assert_not_called()
                assert "Email not configured - skipping notification" in caplog.text

    def test_is_email_configured_true(self, mock_env, tmp_path, monkeypatch):
        """Test is_email_configured returns True when both settings are present."""
        monkeypatch.setenv("HOME", str(tmp_path))

        with patch("prusa_timelapse.load_dotenv"):
            timelapse = PrusaTimelapse()
            assert timelapse.is_email_configured() is True

    def test_is_email_configured_false(self, mock_env, tmp_path, monkeypatch):
        """Test is_email_configured returns False when settings are missing."""
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.delenv("EMAIL_TO")
        monkeypatch.delenv("SMTP_SERVER")

        with patch("prusa_timelapse.load_dotenv"):
            timelapse = PrusaTimelapse()
            assert timelapse.is_email_configured() is False


class TestPrintWorkflow:
    """Test print start/end workflow."""

    def test_handle_print_start(
        self, mock_env, tmp_path, monkeypatch, mock_printer_status_printing
    ):
        """Test print start handling."""
        monkeypatch.setenv("HOME", str(tmp_path))

        with patch("prusa_timelapse.load_dotenv"):
            timelapse = PrusaTimelapse()

            timelapse.handle_print_start("TestPrint", mock_printer_status_printing)

            assert timelapse.is_printing is True
            assert timelapse.current_print_name == "TestPrint"
            assert timelapse.current_print_start is not None
            assert timelapse.image_sequence == []

    def test_handle_print_end_success(self, mock_env, tmp_path, monkeypatch):
        """Test successful print end handling."""
        monkeypatch.setenv("HOME", str(tmp_path))

        with patch("prusa_timelapse.load_dotenv"):
            timelapse = PrusaTimelapse()

            # Set up print state
            timelapse.current_print_name = "TestPrint"
            timelapse.current_print_start = datetime.now()

            # Create fake images (prints dir already exists from init)
            image_dir = timelapse.prints_dir / "2026-01-04-10-00_TestPrint"
            image_dir.mkdir(exist_ok=True)

            for i in range(3):
                img_path = image_dir / f"frame_{i:05d}.jpg"
                img_path.write_bytes(b"fake image")
                timelapse.image_sequence.append(str(img_path))

            with patch.object(timelapse, "create_video", return_value=True):
                with patch.object(timelapse, "send_email"):
                    with patch("shutil.rmtree"):
                        timelapse.handle_print_end()

                        # Verify cleanup happened
                        assert timelapse.image_sequence == []

                        # Verify log file was created
                        log_file = (
                            timelapse.prints_dir / "2026-01-04-10-00_TestPrint.log"
                        )
                        assert log_file.exists()
                        log_content = log_file.read_text()
                        assert "TestPrint" in log_content
                        assert "Frames Captured: 3" in log_content

    def test_handle_print_end_no_images(self, mock_env, tmp_path, monkeypatch):
        """Test print end with no captured images."""
        monkeypatch.setenv("HOME", str(tmp_path))

        with patch("prusa_timelapse.load_dotenv"):
            timelapse = PrusaTimelapse()

            timelapse.is_printing = True
            timelapse.current_print_name = "TestPrint"
            timelapse.image_sequence = []

            timelapse.handle_print_end()

            assert timelapse.is_printing is False

    def test_handle_print_end_cleanup_error(self, mock_env, tmp_path, monkeypatch):
        """Test print end with cleanup error."""
        monkeypatch.setenv("HOME", str(tmp_path))

        with patch("prusa_timelapse.load_dotenv"):
            timelapse = PrusaTimelapse()

            # Set up print state
            timelapse.current_print_name = "TestPrint"
            timelapse.current_print_start = datetime.now()

            # Create fake images
            image_dir = timelapse.prints_dir / "2026-01-04-10-00_TestPrint"
            image_dir.mkdir(exist_ok=True)

            for i in range(2):
                img_path = image_dir / f"frame_{i:05d}.jpg"
                img_path.write_bytes(b"fake image")
                timelapse.image_sequence.append(str(img_path))

            with patch.object(timelapse, "create_video", return_value=True):
                with patch.object(timelapse, "send_email"):
                    with patch(
                        "shutil.rmtree", side_effect=Exception("Permission denied")
                    ):
                        timelapse.handle_print_end()

                        # Should still reset state even with cleanup error
                        assert timelapse.is_printing is False

    def test_handle_print_end_video_failure(self, mock_env, tmp_path, monkeypatch):
        """Test print end with video creation failure."""
        monkeypatch.setenv("HOME", str(tmp_path))

        with patch("prusa_timelapse.load_dotenv"):
            timelapse = PrusaTimelapse()

            # Set up print state
            timelapse.is_printing = True
            timelapse.current_print_name = "TestPrint"
            timelapse.current_print_start = datetime.now()

            # Create fake images
            image_dir = timelapse.prints_dir / "2026-01-04-10-00_TestPrint"
            image_dir.mkdir(exist_ok=True)

            for i in range(2):
                img_path = image_dir / "frame_{i:05d}.jpg"
                img_path.write_bytes(b"fake image")
                timelapse.image_sequence.append(str(img_path))

            with patch.object(timelapse, "create_video", return_value=False):
                timelapse.handle_print_end()

                # State should still be reset
                assert timelapse.is_printing is False

    def test_handle_print_end_without_email(
        self, mock_env, tmp_path, monkeypatch, caplog
    ):
        """Test print end workflow when email is not configured."""
        import logging

        caplog.set_level(logging.INFO)

        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.delenv("EMAIL_TO")
        monkeypatch.delenv("SMTP_SERVER")

        with patch("prusa_timelapse.load_dotenv"):
            timelapse = PrusaTimelapse()
            assert timelapse.is_email_configured() is False

            # Set up print state
            timelapse.is_printing = True
            timelapse.current_print_name = "TestPrint"
            timelapse.current_print_start = datetime.now()

            # Create fake images
            image_dir = timelapse.prints_dir / "2026-01-04-10-00_TestPrint"
            image_dir.mkdir(exist_ok=True)

            for i in range(3):
                img_path = image_dir / f"frame_{i:05d}.jpg"
                img_path.write_bytes(b"fake image")
                timelapse.image_sequence.append(str(img_path))

            with patch("prusa_lib.create_video", return_value=True):
                with patch("shutil.rmtree") as mock_rmtree:
                    with patch("smtplib.SMTP") as mock_smtp:
                        timelapse.handle_print_end()

                        # Video should be created
                        timelapse.prints_dir / "2026-01-04-10-00_TestPrint.mp4"

                        # Email should NOT be attempted
                        mock_smtp.assert_not_called()
                        assert (
                            "Email not configured - timelapse saved to:" in caplog.text
                        )

                        # Cleanup should still happen
                        mock_rmtree.assert_called_once()

                        # State should be reset
                        assert timelapse.is_printing is False
                        assert timelapse.current_print_name is None

    def test_capture_timelapse_frame(self, mock_env, tmp_path, monkeypatch):
        """Test timelapse frame capture."""
        monkeypatch.setenv("HOME", str(tmp_path))

        with patch("prusa_timelapse.load_dotenv"):
            timelapse = PrusaTimelapse()

            # Set up print state
            timelapse.is_printing = True
            timelapse.current_print_name = "TestPrint"
            timelapse.current_print_start = datetime.now()

            with patch.object(
                timelapse, "capture_image", return_value=True
            ) as mock_capture:
                with patch.object(
                    timelapse, "upload_to_prusa_connect", return_value=True
                ):
                    timelapse.capture_timelapse_frame()

                    assert len(timelapse.image_sequence) == 1
                    mock_capture.assert_called_once()

    def test_write_print_log(self, mock_env, tmp_path, monkeypatch):
        """Test print log file creation."""
        monkeypatch.setenv("HOME", str(tmp_path))

        with patch("prusa_timelapse.load_dotenv"):
            timelapse = PrusaTimelapse()

            # Set up some metadata
            timelapse.image_sequence = ["img1.jpg", "img2.jpg", "img3.jpg"]
            timelapse.current_job_metadata = {
                "file": {
                    "display_name": "test_print.gcode",
                    "name": "TEST~1.GCO",
                    "path": "/usb",
                    "size": 1048576,
                }
            }

            log_path = tmp_path / "test_log.log"
            timelapse._write_print_log(log_path, "test_print", 3665)  # 1h 1m 5s

            assert log_path.exists()
            content = log_path.read_text()

            assert "test_print" in content
            assert "1h 1m" in content
            assert "Frames Captured: 3" in content
            assert "test_print.gcode" in content
            assert "1.00 MB" in content


class TestBuildEmailBody:
    """Test email body generation."""

    def test_build_email_body_basic(self, mock_env, tmp_path, monkeypatch):
        """Test email body generation with basic info."""
        monkeypatch.setenv("HOME", str(tmp_path))

        with patch("prusa_timelapse.load_dotenv"):
            timelapse = PrusaTimelapse()
            timelapse.current_print_start = datetime(2026, 1, 4, 10, 0, 0)

            body = timelapse._build_email_body("TestPrint", 3600)

            assert "TestPrint" in body
            assert "1h 0m" in body
            assert "2026-01-04" in body

    def test_build_email_body_with_metadata(
        self, mock_env, tmp_path, monkeypatch, mock_printer_status_printing
    ):
        """Test email body generation with job metadata."""
        monkeypatch.setenv("HOME", str(tmp_path))

        with patch("prusa_timelapse.load_dotenv"):
            timelapse = PrusaTimelapse()
            timelapse.current_print_start = datetime(2026, 1, 4, 10, 0, 0)

            body = timelapse._build_email_body(
                "TestPrint", 3600, mock_printer_status_printing
            )

            assert "TestPrint" in body
            assert "1h 0m" in body

    def test_build_email_body_with_full_metadata(self, mock_env, tmp_path, monkeypatch):
        """Test email body generation with complete job metadata."""
        monkeypatch.setenv("HOME", str(tmp_path))

        # Create metadata with all optional fields
        full_metadata = {
            "job": {
                "file": {
                    "display_name": "DetailedPrint.gcode",
                    "size": 2097152,  # 2 MB
                    "meta": {
                        "filament_type": "PLA",
                        "filament used [g]": 25.5,
                        "filament used [mm]": 8500,
                        "estimated printing time (normal mode)": "2h 30m",
                        "layer_height": "0.20",
                        "nozzle_diameter": "0.4",
                        "temperature": "210",
                        "bed_temperature": "60",
                    },
                }
            },
        }

        with patch("prusa_timelapse.load_dotenv"):
            timelapse = PrusaTimelapse()
            timelapse.current_print_start = datetime(2026, 1, 4, 10, 0, 0)

            body = timelapse._build_email_body("DetailedPrint", 9000, full_metadata)

            assert "DetailedPrint" in body
            assert "2h 30m" in body  # print duration
            assert "PLA" in body
            assert "25.5" in body  # filament weight
            assert "8500" in body  # filament length
            assert "2.00 MB" in body  # file size
            assert "0.20mm" in body  # layer height
            assert "210°C" in body  # nozzle temp
            assert "60°C" in body  # bed temp

    def test_build_email_body_with_time_estimate(self, mock_env, tmp_path, monkeypatch):
        """Test email body with estimated time comparison."""
        monkeypatch.setenv("HOME", str(tmp_path))

        # Metadata with estimated time as integer (seconds)
        metadata_with_estimate = {
            "job": {
                "file": {
                    "display_name": "TimedPrint.gcode",
                    "meta": {
                        "estimated printing time (normal mode)": 7200,  # 2 hours in seconds
                    },
                }
            },
        }

        with patch("prusa_timelapse.load_dotenv"):
            timelapse = PrusaTimelapse()
            timelapse.current_print_start = datetime(2026, 1, 4, 10, 0, 0)

            # Actual print took 2.5 hours (9000 seconds)
            body = timelapse._build_email_body(
                "TimedPrint", 9000, metadata_with_estimate
            )

            assert "Time Comparison" in body
            assert "Estimated: 2h 0m" in body
            assert "Actual: 2h 30m" in body


class TestConnectionErrors:
    """Test connection error handling."""

    def test_connection_error_warnings(self, mock_env, tmp_path, monkeypatch):
        """Test connection error warning messages at different thresholds."""
        monkeypatch.setenv("HOME", str(tmp_path))

        with patch("prusa_timelapse.load_dotenv"):
            timelapse = PrusaTimelapse()

            with patch("requests.get") as mock_get:
                mock_get.side_effect = requests.exceptions.ConnectionError()

                # First error should log
                result = timelapse.get_printer_status()
                assert result is None
                assert timelapse.connection_errors == 1

                # Second error should log
                result = timelapse.get_printer_status()
                assert result is None
                assert timelapse.connection_errors == 2

                # Third error should log warning
                result = timelapse.get_printer_status()
                assert result is None
                assert timelapse.connection_errors == 3

                # Fourth error should log different warning
                result = timelapse.get_printer_status()
                assert result is None
                assert timelapse.connection_errors == 4

    def test_request_exception(self, mock_env, tmp_path, monkeypatch):
        """Test generic request exception handling."""
        monkeypatch.setenv("HOME", str(tmp_path))

        with patch("prusa_timelapse.load_dotenv"):
            timelapse = PrusaTimelapse()

            with patch("requests.get") as mock_get:
                mock_get.side_effect = requests.exceptions.RequestException(
                    "Network error"
                )

                result = timelapse.get_printer_status()
                assert result is None


class TestRunLoop:
    """Test main run loop scenarios."""

    def test_run_keyboard_interrupt(
        self, mock_env, tmp_path, monkeypatch, mock_printer_status_idle
    ):
        """Test graceful shutdown on KeyboardInterrupt."""
        monkeypatch.setenv("HOME", str(tmp_path))

        with patch("prusa_timelapse.load_dotenv"):
            timelapse = PrusaTimelapse()

            with patch.object(
                timelapse, "get_printer_status", return_value=mock_printer_status_idle
            ):
                with patch("time.sleep", side_effect=KeyboardInterrupt):
                    timelapse.run()
                    # Should exit gracefully without error

    def test_run_keyboard_interrupt_while_printing(
        self, mock_env, tmp_path, monkeypatch, mock_printer_status_printing
    ):
        """Test shutdown while printing saves the video."""
        monkeypatch.setenv("HOME", str(tmp_path))

        with patch("prusa_timelapse.load_dotenv"):
            timelapse = PrusaTimelapse()
            timelapse.is_printing = True
            timelapse.current_print_name = "TestPrint"
            timelapse.current_print_dir = tmp_path / "current_print"
            timelapse.current_print_dir.mkdir()

            with patch.object(
                timelapse,
                "get_printer_status",
                return_value=mock_printer_status_printing,
            ):
                with patch.object(timelapse, "handle_print_end") as mock_end:
                    with patch("time.sleep", side_effect=KeyboardInterrupt):
                        timelapse.run()
                        # Should call handle_print_end to save progress
                        mock_end.assert_called_once()

    def test_run_unexpected_error(self, mock_env, tmp_path, monkeypatch):
        """Test handling of unexpected errors in main loop."""
        monkeypatch.setenv("HOME", str(tmp_path))

        with patch("prusa_timelapse.load_dotenv"):
            timelapse = PrusaTimelapse()

            with patch.object(
                timelapse, "get_printer_status", side_effect=RuntimeError("Unexpected")
            ):
                with patch("sys.exit") as mock_exit:
                    timelapse.run()
                    mock_exit.assert_called_once_with(1)
