"""Tests for prusa_lib.py - shared utility functions"""

import sys
import os
import requests
from unittest.mock import MagicMock, patch
from io import BytesIO


# Import the module to test
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import prusa_lib  # noqa: E402


class TestRotateImage:
    """Test rotate_image function."""

    def test_rotate_image_no_rotation(self, tmp_path):
        """Test that 0 rotation returns True without modifying image."""
        test_image = tmp_path / "test.jpg"
        test_image.write_bytes(b"fake image data")

        result = prusa_lib.rotate_image(str(test_image), 0)
        assert result is True

    def test_rotate_image_90_degrees(self, tmp_path):
        """Test 90 degree rotation."""
        test_image = tmp_path / "test.jpg"
        test_image.write_bytes(b"fake image data")

        mock_img = MagicMock()
        mock_rotated = MagicMock()

        with patch("prusa_lib.Image.open", return_value=mock_img):
            mock_img.rotate.return_value = mock_rotated

            result = prusa_lib.rotate_image(str(test_image), 90)

            assert result is True
            mock_img.rotate.assert_called_once_with(-90, expand=True)
            mock_rotated.save.assert_called_once_with(str(test_image))

    def test_rotate_image_invalid_angle(self, tmp_path):
        """Test invalid rotation angle."""
        test_image = tmp_path / "test.jpg"
        test_image.write_bytes(b"fake image data")

        result = prusa_lib.rotate_image(str(test_image), 45)
        assert result is False

    def test_rotate_image_exception(self, tmp_path):
        """Test exception during rotation."""
        test_image = tmp_path / "test.jpg"
        test_image.write_bytes(b"fake image data")

        with patch("prusa_lib.Image.open", side_effect=Exception("Test error")):
            result = prusa_lib.rotate_image(str(test_image), 90)
            assert result is False


class TestRotateImageBytes:
    """Test rotate_image_bytes function."""

    def test_rotate_bytes_no_rotation(self):
        """Test that 0 rotation returns original data."""
        image_data = b"fake image data"
        result = prusa_lib.rotate_image_bytes(image_data, 0)
        assert result == image_data

    def test_rotate_bytes_90_degrees(self):
        """Test 90 degree rotation of bytes."""
        image_data = b"fake image data"
        mock_img = MagicMock()
        mock_rotated = MagicMock()

        with patch("prusa_lib.Image.open", return_value=mock_img):
            mock_img.rotate.return_value = mock_rotated

            def mock_save(f, format):
                f.write(b"rotated data")

            mock_rotated.save = mock_save

            with patch("prusa_lib.BytesIO") as mock_bytesio:
                mock_input = MagicMock()
                mock_output = BytesIO()
                mock_bytesio.side_effect = [mock_input, mock_output]

                result = prusa_lib.rotate_image_bytes(image_data, 90)

                assert result == b"rotated data"
                mock_img.rotate.assert_called_once_with(-90, expand=True)

    def test_rotate_bytes_invalid_angle(self):
        """Test invalid rotation angle."""
        image_data = b"fake image data"
        result = prusa_lib.rotate_image_bytes(image_data, 45)
        assert result == image_data

    def test_rotate_bytes_exception(self):
        """Test exception during rotation."""
        image_data = b"fake image data"

        with patch("prusa_lib.Image.open", side_effect=Exception("Test error")):
            result = prusa_lib.rotate_image_bytes(image_data, 90)
            assert result == image_data


class TestCheckCommand:
    """Test command availability checking."""

    def test_check_command_exists(self):
        """Test checking for existing command."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0, stdout="version info", stderr=""
            )

            result = prusa_lib.check_command("python3", "Python 3")

            assert result is True
            mock_run.assert_called_once()

    def test_check_command_not_found(self):
        """Test checking for missing command."""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = FileNotFoundError()

            result = prusa_lib.check_command("nonexistent", "Nonexistent")

            assert result is False

    def test_check_command_ffmpeg_timeout(self):
        """Test ffmpeg check uses longer timeout."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0, stdout="ffmpeg version", stderr=""
            )

            result = prusa_lib.check_command("ffmpeg", "FFmpeg")

            assert result is True
            # Verify timeout was set to 15 for ffmpeg
            call_kwargs = mock_run.call_args[1]
            assert call_kwargs["timeout"] == 15

    def test_check_command_other_timeout(self):
        """Test command timeout is configurable."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="version", stderr="")

            result = prusa_lib.check_command("rpicam-still", "rpicam-apps", timeout=5)

            assert result is True
            call_kwargs = mock_run.call_args[1]
            assert call_kwargs["timeout"] == 5


class TestCheckPythonPackage:
    """Test Python package checking."""

    def test_check_package_installed(self):
        """Test checking for installed package."""
        with patch("builtins.__import__") as mock_import:
            mock_import.return_value = MagicMock()

            result = prusa_lib.check_python_package("requests")

            assert result is True
            mock_import.assert_called_once_with("requests")

    def test_check_package_not_installed(self):
        """Test checking for missing package."""
        with patch("builtins.__import__") as mock_import:
            mock_import.side_effect = ImportError()

            result = prusa_lib.check_python_package("nonexistent")

            assert result is False

    def test_check_package_different_import_name(self):
        """Test checking package with different import name."""
        with patch("builtins.__import__") as mock_import:
            mock_import.return_value = MagicMock()

            result = prusa_lib.check_python_package("python-dotenv", "dotenv")

            assert result is True
            mock_import.assert_called_once_with("dotenv")


class TestCheckCamera:
    """Test camera detection."""

    def test_camera_detected(self):
        """Test successful camera detection."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0, stderr="Available cameras:\n  0 : imx219"
            )

            result = prusa_lib.check_camera()

            assert result is True

    def test_camera_not_detected(self):
        """Test no camera detected."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0, stderr="No cameras available"
            )

            result = prusa_lib.check_camera()

            assert result is False

    def test_camera_command_not_found(self):
        """Test rpicam-still not installed."""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = FileNotFoundError()

            result = prusa_lib.check_camera()

            assert result is False


class TestValidateEnvConfig:
    """Test validate_env_config function."""

    def test_validate_all_valid(self):
        """Test with all valid environment variables."""
        env_vars = {
            "PRUSA_PRINTER_HOST": "http://192.168.1.100",
            "PRUSA_API_KEY": "my_api_key",
            "EMAIL_FROM": "test@example.com",
        }

        valid, missing = prusa_lib.validate_env_config(env_vars)

        assert valid is True
        assert missing == []

    def test_validate_missing_value(self):
        """Test with missing environment variable."""
        env_vars = {
            "PRUSA_PRINTER_HOST": "http://192.168.1.100",
            "PRUSA_API_KEY": "",
            "EMAIL_FROM": "test@example.com",
        }

        valid, missing = prusa_lib.validate_env_config(env_vars)

        assert valid is False
        assert "PRUSA_API_KEY" in missing

    def test_validate_placeholder_value(self):
        """Test with placeholder values."""
        env_vars = {
            "PRUSA_PRINTER_HOST": "http://192.168.1.100",
            "PRUSA_API_KEY": "your_api_key_here",
            "EMAIL_FROM": "test@example.com",
        }

        valid, missing = prusa_lib.validate_env_config(env_vars)

        assert valid is False
        assert "PRUSA_API_KEY" in missing


class TestValidateRotation:
    """Test validate_rotation function."""

    def test_validate_rotation_valid_values(self):
        """Test valid rotation values."""
        assert prusa_lib.validate_rotation("0") == 0
        assert prusa_lib.validate_rotation("90") == 90
        assert prusa_lib.validate_rotation("180") == 180
        assert prusa_lib.validate_rotation("270") == 270

    def test_validate_rotation_invalid_value(self):
        """Test invalid rotation value returns 0."""
        result = prusa_lib.validate_rotation("45")
        assert result == 0

    def test_validate_rotation_invalid_string(self):
        """Test non-numeric string returns 0."""
        result = prusa_lib.validate_rotation("abc")
        assert result == 0


class TestSendEmail:
    """Test send_email function."""

    def test_send_email_success(self, monkeypatch):
        """Test successful email sending without authentication."""
        mock_smtp_instance = MagicMock()
        mock_smtp_class = MagicMock(return_value=mock_smtp_instance)

        with patch("smtplib.SMTP", mock_smtp_class):
            result = prusa_lib.send_email(
                smtp_server="smtp.example.com",
                smtp_port="587",
                email_from="from@example.com",
                email_to="to@example.com",
                subject="Test Subject",
                html_body="<p>Test body</p>",
                attachment_path=None,
                smtp_username=None,
                smtp_password=None,
            )

            assert result is True

    def test_send_email_with_auth(self, monkeypatch):
        """Test email sending with SMTP authentication."""
        mock_smtp_instance = MagicMock()
        mock_smtp_class = MagicMock(return_value=mock_smtp_instance)

        with patch("smtplib.SMTP", mock_smtp_class):
            result = prusa_lib.send_email(
                smtp_server="smtp.example.com",
                smtp_port="587",
                email_from="from@example.com",
                email_to="to@example.com",
                subject="Test Subject",
                html_body="<p>Test body</p>",
                attachment_path=None,
                smtp_username="user@example.com",
                smtp_password="password123",
            )

            assert result is True

    def test_send_email_with_attachment(self, tmp_path, monkeypatch):
        """Test email sending with attachment."""
        # Create a test attachment file
        attachment = tmp_path / "test_video.mp4"
        attachment.write_bytes(b"fake video data")

        mock_smtp_instance = MagicMock()
        mock_smtp_class = MagicMock(return_value=mock_smtp_instance)

        with patch("smtplib.SMTP", mock_smtp_class):
            result = prusa_lib.send_email(
                smtp_server="smtp.example.com",
                smtp_port="587",
                email_from="from@example.com",
                email_to="to@example.com",
                subject="Test Subject",
                html_body="<p>Test body</p>",
                attachment_path=str(attachment),
                smtp_username=None,
                smtp_password=None,
            )

            assert result is True

    def test_send_email_exception(self, monkeypatch):
        """Test email sending with exception."""
        with patch("smtplib.SMTP", side_effect=Exception("SMTP error")):
            result = prusa_lib.send_email(
                smtp_server="smtp.example.com",
                smtp_port="587",
                email_from="from@example.com",
                email_to="to@example.com",
                subject="Test Subject",
                html_body="<p>Test body</p>",
                attachment_path=None,
                smtp_username=None,
                smtp_password=None,
            )

            assert result is False


class TestGetJobInfo:
    """Test get_job_info function."""

    def test_get_job_info_success(self):
        """Test successful job info retrieval."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "id": 123,
            "state": "PRINTING",
            "file": {"display_name": "test.gcode", "name": "TEST~1.GCO"},
        }

        with patch("requests.get", return_value=mock_response):
            result = prusa_lib.get_job_info("192.168.1.100", "test_key")

            assert result is not None
            assert result["id"] == 123
            assert result["file"]["display_name"] == "test.gcode"

    def test_get_job_info_timeout(self):
        """Test job info retrieval timeout."""
        with patch("requests.get", side_effect=requests.exceptions.Timeout()):
            result = prusa_lib.get_job_info("192.168.1.100", "test_key")
            assert result is None

    def test_get_job_info_connection_error(self):
        """Test job info retrieval connection error."""
        with patch("requests.get", side_effect=requests.exceptions.ConnectionError()):
            result = prusa_lib.get_job_info("192.168.1.100", "test_key")
            assert result is None

    def test_get_job_info_http_error(self):
        """Test job info retrieval HTTP error."""
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError()

        with patch("requests.get", return_value=mock_response):
            result = prusa_lib.get_job_info("192.168.1.100", "test_key")
            assert result is None


class TestUploadToPrusaConnect:
    """Test upload_to_prusa_connect function."""

    def test_upload_missing_credentials(self, tmp_path):
        """Test upload with missing token or fingerprint."""
        test_image = tmp_path / "test.jpg"
        test_image.write_bytes(b"fake jpg")

        # Missing token
        result = prusa_lib.upload_to_prusa_connect(
            str(test_image), "", "fingerprint", rotation=0
        )
        assert result is False

        # Missing fingerprint
        result = prusa_lib.upload_to_prusa_connect(
            str(test_image), "token", "", rotation=0
        )
        assert result is False

    def test_upload_with_rotation(self, tmp_path):
        """Test upload with image rotation."""
        test_image = tmp_path / "test.jpg"
        test_image.write_bytes(b"fake jpg")

        mock_response = MagicMock()
        mock_response.status_code = 200

        with patch("requests.put", return_value=mock_response):
            with patch(
                "prusa_lib.rotate_image_bytes", return_value=b"rotated jpg"
            ) as mock_rotate:
                result = prusa_lib.upload_to_prusa_connect(
                    str(test_image), "token", "fingerprint", rotation=90
                )

                assert result is True
                mock_rotate.assert_called_once_with(b"fake jpg", 90)

    def test_upload_generic_exception(self, tmp_path):
        """Test upload with generic exception."""
        test_image = tmp_path / "test.jpg"
        test_image.write_bytes(b"fake jpg")

        with patch("builtins.open", side_effect=Exception("File error")):
            result = prusa_lib.upload_to_prusa_connect(
                str(test_image), "token", "fingerprint"
            )

            assert result is False


class TestCreateVideo:
    """Test video creation functions."""

    def test_create_video_simple_path(self, tmp_path):
        """Test simple video creation for small number of frames."""
        # Create test frames (below batch_size threshold)
        frame_dir = tmp_path / "frames"
        frame_dir.mkdir()
        for i in range(50):
            (frame_dir / f"frame_{i:05d}.jpg").write_bytes(b"fake jpg")

        output_path = tmp_path / "output.mp4"

        with patch("subprocess.run") as mock_run:
            with patch("os.path.exists", return_value=True):
                with patch("os.path.getsize", return_value=1024 * 1024):
                    mock_result = MagicMock()
                    mock_result.returncode = 0
                    mock_result.stderr = ""
                    mock_run.return_value = mock_result

                    result = prusa_lib.create_video(
                        frame_dir, str(output_path), fps=30, quality=23, batch_size=150
                    )

                    assert result is True
                    # Should call simple method (single ffmpeg command)
                    assert mock_run.call_count == 1
                    call_args = mock_run.call_args[0][0]
                    assert "ffmpeg" in call_args
                    assert "-pattern_type" in call_args
                    assert "glob" in call_args

    def test_create_video_batched_path(self, tmp_path):
        """Test batched video creation for large number of frames."""
        # Create test frames (above batch_size threshold)
        frame_dir = tmp_path / "frames"
        frame_dir.mkdir()
        for i in range(350):  # More than batch_size of 150
            (frame_dir / f"frame_{i:05d}.jpg").write_bytes(b"fake jpg")

        output_path = tmp_path / "output.mp4"

        with patch("subprocess.run") as mock_run:
            with patch("os.path.exists", return_value=True):
                with patch("os.path.getsize", return_value=5 * 1024 * 1024):
                    mock_result = MagicMock()
                    mock_result.returncode = 0
                    mock_result.stderr = ""
                    mock_run.return_value = mock_result

                    result = prusa_lib.create_video(
                        frame_dir, str(output_path), fps=30, quality=23, batch_size=150
                    )

                    assert result is True
                    # Should create 3 batches (350 frames / 150 = 2.33 -> 3 batches)
                    # Plus 1 final concatenation = 4 calls total
                    assert mock_run.call_count == 4

    def test_create_video_no_frames(self, tmp_path):
        """Test video creation with no frames."""
        frame_dir = tmp_path / "frames"
        frame_dir.mkdir()

        output_path = tmp_path / "output.mp4"

        result = prusa_lib.create_video(frame_dir, str(output_path), fps=30, quality=23)

        assert result is False

    def test_create_video_with_rotation(self, tmp_path):
        """Test video creation with rotation filter."""
        frame_dir = tmp_path / "frames"
        frame_dir.mkdir()
        for i in range(10):
            (frame_dir / f"frame_{i:05d}.jpg").write_bytes(b"fake jpg")

        output_path = tmp_path / "output.mp4"

        with patch("subprocess.run") as mock_run:
            with patch("os.path.exists", return_value=True):
                with patch("os.path.getsize", return_value=1024 * 1024):
                    mock_result = MagicMock()
                    mock_result.returncode = 0
                    mock_result.stderr = ""
                    mock_run.return_value = mock_result

                    result = prusa_lib.create_video(
                        frame_dir, str(output_path), rotation=90
                    )

                    assert result is True
                    call_args = mock_run.call_args[0][0]
                    assert "-vf" in call_args
                    assert "transpose=1" in call_args

    def test_create_video_batch_failure(self, tmp_path):
        """Test batched video creation with segment failure."""
        frame_dir = tmp_path / "frames"
        frame_dir.mkdir()
        for i in range(200):
            (frame_dir / f"frame_{i:05d}.jpg").write_bytes(b"fake jpg")

        output_path = tmp_path / "output.mp4"

        with patch("subprocess.run") as mock_run:
            # First batch fails
            mock_result = MagicMock()
            mock_result.returncode = 1
            mock_result.stderr = "Encoding error"
            mock_run.return_value = mock_result

            result = prusa_lib.create_video(frame_dir, str(output_path), batch_size=100)

            assert result is False

    def test_create_video_concat_failure(self, tmp_path):
        """Test batched video creation with concatenation failure."""
        frame_dir = tmp_path / "frames"
        frame_dir.mkdir()
        for i in range(200):
            (frame_dir / f"frame_{i:05d}.jpg").write_bytes(b"fake jpg")

        output_path = tmp_path / "output.mp4"

        with patch("subprocess.run") as mock_run:
            # Batch creation succeeds, concat fails
            def side_effect(*args, **kwargs):
                mock_result = MagicMock()
                if mock_run.call_count <= 2:  # Batches succeed
                    mock_result.returncode = 0
                    mock_result.stderr = ""
                else:  # Concatenation fails
                    mock_result.returncode = 1
                    mock_result.stderr = "Concat error"
                return mock_result

            mock_run.side_effect = side_effect

            result = prusa_lib.create_video(frame_dir, str(output_path), batch_size=100)

            assert result is False

    def test_create_video_exception_handling(self, tmp_path):
        """Test exception handling in video creation."""
        frame_dir = tmp_path / "frames"
        frame_dir.mkdir()
        for i in range(10):
            (frame_dir / f"frame_{i:05d}.jpg").write_bytes(b"fake jpg")

        output_path = tmp_path / "output.mp4"

        with patch("subprocess.run", side_effect=Exception("Unexpected error")):
            result = prusa_lib.create_video(frame_dir, str(output_path))

            assert result is False


class TestCreateVideoBatchedHelpers:
    """Test internal batch processing helper functions."""

    def test_create_video_simple_success(self, tmp_path):
        """Test _create_video_simple helper function."""
        frame_dir = tmp_path / "frames"
        frame_dir.mkdir()
        for i in range(10):
            (frame_dir / f"frame_{i:05d}.jpg").write_bytes(b"fake jpg")

        output_path = tmp_path / "output.mp4"

        with patch("subprocess.run") as mock_run:
            with patch("os.path.exists", return_value=True):
                with patch("os.path.getsize", return_value=1024 * 1024):
                    mock_result = MagicMock()
                    mock_result.returncode = 0
                    mock_result.stderr = ""
                    mock_run.return_value = mock_result

                    result = prusa_lib._create_video_simple(
                        frame_dir,
                        str(output_path),
                        fps=30,
                        quality=23,
                        rotation=0,
                        timeout=300,
                    )

                    assert result is True
                    mock_run.assert_called_once()

    def test_create_video_batched_success(self, tmp_path):
        """Test _create_video_batched helper function."""
        frame_dir = tmp_path / "frames"
        frame_dir.mkdir()

        # Create frame files
        frame_files = []
        for i in range(250):
            frame_path = frame_dir / f"frame_{i:05d}.jpg"
            frame_path.write_bytes(b"fake jpg")
            frame_files.append(frame_path)

        output_path = tmp_path / "output.mp4"

        with patch("subprocess.run") as mock_run:
            with patch("os.path.exists", return_value=True):
                with patch("os.path.getsize", return_value=3 * 1024 * 1024):
                    mock_result = MagicMock()
                    mock_result.returncode = 0
                    mock_result.stderr = ""
                    mock_run.return_value = mock_result

                    result = prusa_lib._create_video_batched(
                        frame_files,
                        str(output_path),
                        fps=30,
                        quality=23,
                        rotation=0,
                        timeout=300,
                        batch_size=100,
                    )

                    assert result is True
                    # 3 batches + 1 concat = 4 calls
                    assert mock_run.call_count == 4

    def test_create_video_batched_cleanup(self, tmp_path):
        """Test that batched processing cleans up temporary files."""
        frame_dir = tmp_path / "frames"
        frame_dir.mkdir()

        frame_files = []
        for i in range(200):
            frame_path = frame_dir / f"frame_{i:05d}.jpg"
            frame_path.write_bytes(b"fake jpg")
            frame_files.append(frame_path)

        output_path = tmp_path / "output.mp4"

        with patch("subprocess.run") as mock_run:
            with patch("os.path.exists", return_value=True):
                with patch("os.path.getsize", return_value=2 * 1024 * 1024):
                    mock_result = MagicMock()
                    mock_result.returncode = 0
                    mock_result.stderr = ""
                    mock_run.return_value = mock_result

                    result = prusa_lib._create_video_batched(
                        frame_files,
                        str(output_path),
                        fps=30,
                        quality=23,
                        rotation=0,
                        timeout=300,
                        batch_size=100,
                    )

                    assert result is True

                    # Verify temp directory was cleaned up
                    temp_dir = output_path.parent / f".tmp_{output_path.stem}"
                    assert not temp_dir.exists()

    def test_create_video_batched_exception_in_batch(self, tmp_path):
        """Test exception handling during batch processing."""
        frame_dir = tmp_path / "frames"
        frame_dir.mkdir()

        frame_files = []
        for i in range(200):
            frame_path = frame_dir / f"frame_{i:05d}.jpg"
            frame_path.write_bytes(b"fake jpg")
            frame_files.append(frame_path)

        output_path = tmp_path / "output.mp4"

        with patch("subprocess.run", side_effect=Exception("Unexpected error")):
            result = prusa_lib._create_video_batched(
                frame_files,
                str(output_path),
                fps=30,
                quality=23,
                rotation=0,
                timeout=300,
                batch_size=100,
            )

            assert result is False

    def test_create_video_batched_cleanup_failure(self, tmp_path):
        """Test that cleanup failures are handled gracefully."""
        frame_dir = tmp_path / "frames"
        frame_dir.mkdir()

        frame_files = []
        for i in range(200):
            frame_path = frame_dir / f"frame_{i:05d}.jpg"
            frame_path.write_bytes(b"fake jpg")
            frame_files.append(frame_path)

        output_path = tmp_path / "output.mp4"

        with patch("subprocess.run") as mock_run:
            with patch("os.path.exists", return_value=True):
                with patch("os.path.getsize", return_value=2 * 1024 * 1024):
                    mock_result = MagicMock()
                    mock_result.returncode = 0
                    mock_result.stderr = ""
                    mock_run.return_value = mock_result

                    # Mock shutil.rmtree to fail
                    with patch(
                        "shutil.rmtree", side_effect=PermissionError("Cleanup failed")
                    ):
                        result = prusa_lib._create_video_batched(
                            frame_files,
                            str(output_path),
                            fps=30,
                            quality=23,
                            rotation=0,
                            timeout=300,
                            batch_size=100,
                        )

                        # Should still succeed even if cleanup fails
                        assert result is True
