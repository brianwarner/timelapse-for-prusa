#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Brian Warner
"""
Prusa Timelapse Library - Shared utility functions

This module provides reusable functions for camera operations, video creation,
API interactions, and system validation used by both the main timelapse script
and setup utilities.
"""

import os
import subprocess
import shlex
import logging
from pathlib import Path
from io import BytesIO
import requests
from PIL import Image

logger = logging.getLogger(__name__)


# ============================================================================
# Camera & Image Operations
# ============================================================================


def sanitize_rpicam_params(params):
    """
    Sanitize rpicam-still extra parameters for security.

    Args:
        params (str): Extra command-line parameters

    Returns:
        str: Sanitized parameters

    Raises:
        ValueError: If dangerous patterns are detected
    """
    if not params:
        return ""

    # Check for command injection patterns
    dangerous_patterns = ["&&", ";", "||", "`", "$(", "${", "\n", "\r"]
    for pattern in dangerous_patterns:
        if pattern in params:
            error_msg = f"Dangerous pattern '{pattern}' detected in RPICAM_EXTRA_PARAMS"
            logger.error(error_msg)
            raise ValueError(error_msg)

    # Warn if conflicting parameters are used
    conflicting = ["--output", "--width", "--height"]
    for param in conflicting:
        if param in params:
            logger.warning(
                f"Parameter '{param}' in RPICAM_EXTRA_PARAMS will be ignored (set by configuration)"
            )

    return params


def capture_image(
    output_path,
    width=1920,
    height=1080,
    extra_params="",
    lens_position=None,
    timeout=10,
):
    """
    Capture an image using rpicam-still.

    Args:
        output_path (str): Path where image should be saved
        width (int): Image width in pixels
        height (int): Image height in pixels
        extra_params (str): Additional rpicam-still parameters
        lens_position (float): Lens position value (calculated from focus distance)
        timeout (int): Command timeout in seconds

    Returns:
        bool: True if capture was successful, False otherwise
    """
    try:
        # Build command
        cmd = [
            "rpicam-still",
            "--width",
            str(width),
            "--height",
            str(height),
            "--output",
            output_path,
            "--nopreview",
            "--autofocus-mode",
            "manual",
            "--timeout",
            "1",  # 1ms timeout
            "--immediate",  # Capture immediately
        ]

        # Add lens position if provided
        if lens_position is not None:
            cmd.extend(["--lens-position", str(lens_position)])

        # Add extra parameters if provided
        if extra_params:
            sanitized = sanitize_rpicam_params(extra_params)
            if sanitized:
                cmd.extend(shlex.split(sanitized))

        # Log the command being executed (INFO level for visibility)
        logger.info(f"Capturing image: {' '.join(cmd)}")

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)

        if result.returncode == 0 and os.path.exists(output_path):
            logger.debug(f"Captured image: {output_path}")
            return True
        else:
            logger.error(f"Failed to capture image: {result.stderr}")
            return False

    except subprocess.TimeoutExpired:
        logger.error(f"Image capture timed out after {timeout}s")
        return False
    except Exception as e:
        logger.error(f"Error capturing image: {e}")
        return False


def rotate_image(image_path, rotation):
    """
    Rotate an image file in-place.

    Args:
        image_path (str): Path to image file
        rotation (int): Rotation angle in degrees (0, 90, 180, 270)

    Returns:
        bool: True if rotation was successful, False otherwise
    """
    if rotation == 0:
        return True  # No rotation needed

    if rotation not in [90, 180, 270]:
        logger.error(f"Invalid rotation angle: {rotation}. Must be 0, 90, 180, or 270")
        return False

    try:
        img = Image.open(image_path)
        rotated = img.rotate(-rotation, expand=True)
        rotated.save(image_path)
        logger.debug(f"Rotated image {rotation} degrees: {image_path}")
        return True
    except Exception as e:
        logger.error(f"Error rotating image: {e}")
        return False


def rotate_image_bytes(image_data, rotation):
    """
    Rotate image data in memory and return as bytes.

    Args:
        image_data (bytes): Image file data
        rotation (int): Rotation angle in degrees (0, 90, 180, 270)

    Returns:
        bytes: Rotated image data, or original if rotation=0 or error
    """
    if rotation == 0:
        return image_data

    if rotation not in [90, 180, 270]:
        logger.error(f"Invalid rotation angle: {rotation}")
        return image_data

    try:
        img = Image.open(BytesIO(image_data))
        rotated = img.rotate(-rotation, expand=True)

        output = BytesIO()
        rotated.save(output, format="JPEG")
        return output.getvalue()
    except Exception as e:
        logger.error(f"Error rotating image bytes: {e}")
        return image_data


def create_video(
    image_dir,
    output_path,
    fps=30,
    quality=23,
    rotation=0,
    timeout=300,
    batch_size=150,
):
    """
    Create a timelapse video from image sequence using ffmpeg.
    Uses batch processing for memory efficiency on systems with limited RAM.

    Args:
        image_dir (str or Path): Directory containing frame_*.jpg images
        output_path (str): Path for output video file
        fps (int): Frames per second
        quality (int): CRF quality value (0-51, lower = better)
        rotation (int): Rotation angle in degrees (0, 90, 180, 270)
        timeout (int): Command timeout in seconds
        batch_size (int): Number of frames per batch (reduces memory usage)

    Returns:
        bool: True if video creation was successful, False otherwise
    """
    try:
        image_dir = Path(image_dir)

        # Get sorted list of frame files
        frame_files = sorted(image_dir.glob("frame_*.jpg"))
        num_frames = len(frame_files)

        if num_frames == 0:
            logger.error(f"No frame files found in {image_dir}")
            return False

        logger.info(f"Found {num_frames} frames to process")

        # Use batch processing if we have many frames (memory efficient for Pi Zero 2)
        if num_frames > batch_size:
            logger.info(
                f"Using batch processing ({batch_size} frames/batch) "
                "to minimize memory usage"
            )
            return _create_video_batched(
                frame_files, output_path, fps, quality, rotation, timeout, batch_size
            )
        else:
            # Use simple single-pass method for small frame counts
            return _create_video_simple(
                image_dir, output_path, fps, quality, rotation, timeout
            )

    except Exception as e:
        logger.error(f"Error creating video: {e}")
        return False


def _create_video_simple(image_dir, output_path, fps, quality, rotation, timeout):
    """
    Create video using single ffmpeg pass (original method).
    Suitable for small numbers of frames.
    """
    try:
        # Build ffmpeg command
        cmd = [
            "ffmpeg",
            "-y",  # Overwrite output file if it exists
            "-framerate",
            str(fps),
            "-pattern_type",
            "glob",
            "-i",
            str(image_dir / "frame_*.jpg"),
        ]

        # Add rotation filter if needed
        if rotation == 90:
            cmd.extend(["-vf", "transpose=1"])  # 90 degrees clockwise
        elif rotation == 180:
            cmd.extend(["-vf", "transpose=1,transpose=1"])  # 180 degrees
        elif rotation == 270:
            cmd.extend(["-vf", "transpose=2"])  # 90 degrees counter-clockwise

        # Add encoding parameters
        cmd.extend(
            [
                "-c:v",
                "libx264",
                "-crf",
                str(quality),
                "-pix_fmt",
                "yuv420p",
                "-movflags",
                "+faststart",  # Optimize for web playback
                str(output_path),
            ]
        )

        # Log the command being executed (INFO level for visibility)
        logger.info(f"Creating video: {' '.join(cmd)}")

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)

        if result.returncode == 0 and os.path.exists(output_path):
            file_size_mb = os.path.getsize(output_path) / (1024 * 1024)
            logger.info(
                f"Video created successfully: {output_path} ({file_size_mb:.2f} MB)"
            )
            return True
        else:
            logger.error(f"Failed to create video: {result.stderr}")
            return False

    except Exception as e:
        logger.error(f"Error in simple video creation: {e}")
        return False


def _create_video_batched(
    frame_files, output_path, fps, quality, rotation, timeout, batch_size
):
    """
    Create video by processing frames in batches and concatenating.
    Memory-efficient approach for systems with limited RAM (e.g., Pi Zero 2).

    Args:
        frame_files (list): Sorted list of Path objects for frame files
        output_path (str): Path for output video file
        fps (int): Frames per second
        quality (int): CRF quality value
        rotation (int): Rotation angle in degrees
        timeout (int): Command timeout in seconds
        batch_size (int): Number of frames per batch

    Returns:
        bool: True if successful, False otherwise
    """
    temp_segments = []
    output_path = Path(output_path)
    temp_dir = output_path.parent / f".tmp_{output_path.stem}"

    try:
        # Create temporary directory for segment files
        temp_dir.mkdir(exist_ok=True)
        logger.debug(f"Created temporary directory: {temp_dir}")

        # Process frames in batches
        num_batches = (len(frame_files) + batch_size - 1) // batch_size
        logger.info(f"Processing {num_batches} batches...")

        for batch_idx in range(num_batches):
            start_idx = batch_idx * batch_size
            end_idx = min(start_idx + batch_size, len(frame_files))
            batch_frames = frame_files[start_idx:end_idx]

            segment_path = temp_dir / f"segment_{batch_idx:03d}.mp4"
            temp_segments.append(segment_path)

            logger.info(
                f"Processing batch {batch_idx + 1}/{num_batches} "
                f"(frames {start_idx} to {end_idx - 1})"
            )

            # Create temporary file list for this batch
            # The concat demuxer needs duration hints for image files
            file_list_path = temp_dir / f"batch_{batch_idx:03d}_files.txt"
            frame_duration = 1.0 / fps  # Duration of each frame in seconds

            with open(file_list_path, "w") as f:
                for frame_file in batch_frames:
                    # Concat demuxer format with duration for image sequences
                    f.write(f"file '{frame_file.absolute()}'\n")
                    f.write(f"duration {frame_duration:.6f}\n")
                # Add the last frame again without duration (concat demuxer requirement)
                if batch_frames:
                    f.write(f"file '{batch_frames[-1].absolute()}'\n")

            # Build ffmpeg command for this batch
            cmd = [
                "ffmpeg",
                "-y",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                str(file_list_path),
            ]

            # Add rotation filter if needed
            if rotation == 90:
                cmd.extend(["-vf", "transpose=1"])
            elif rotation == 180:
                cmd.extend(["-vf", "transpose=1,transpose=1"])
            elif rotation == 270:
                cmd.extend(["-vf", "transpose=2"])

            # Add encoding parameters
            cmd.extend(
                [
                    "-c:v",
                    "libx264",
                    "-crf",
                    str(quality),
                    "-pix_fmt",
                    "yuv420p",
                    str(segment_path),
                ]
            )

            logger.debug(f"Batch command: {' '.join(cmd)}")

            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=timeout
            )

            if result.returncode != 0:
                logger.error(f"Failed to create segment {batch_idx}: {result.stderr}")
                return False

            # Clean up batch file list
            file_list_path.unlink()

        # Concatenate all segments into final video
        logger.info(f"Concatenating {len(temp_segments)} segments into final video...")

        concat_list_path = temp_dir / "concat_list.txt"
        with open(concat_list_path, "w") as f:
            for segment in temp_segments:
                f.write(f"file '{segment.absolute()}'\n")

        cmd = [
            "ffmpeg",
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(concat_list_path),
            "-c",
            "copy",  # Copy codec (no re-encoding for speed)
            "-movflags",
            "+faststart",
            str(output_path),
        ]

        logger.info(f"Final concatenation: {' '.join(cmd)}")

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)

        if result.returncode == 0 and os.path.exists(output_path):
            file_size_mb = os.path.getsize(output_path) / (1024 * 1024)
            logger.info(
                f"Video created successfully: {output_path} ({file_size_mb:.2f} MB)"
            )
            return True
        else:
            logger.error(f"Failed to concatenate segments: {result.stderr}")
            return False

    except Exception as e:
        logger.error(f"Error in batched video creation: {e}")
        return False

    finally:
        # Clean up temporary files
        if temp_dir.exists():
            try:
                import shutil

                shutil.rmtree(temp_dir)
                logger.debug(f"Cleaned up temporary directory: {temp_dir}")
            except Exception as e:
                logger.warning(f"Failed to clean up temp directory {temp_dir}: {e}")


# ============================================================================
# Prusa Connect Integration
# ============================================================================


def upload_to_prusa_connect(image_path, token, fingerprint, rotation=0, timeout=10):
    """
    Upload an image to Prusa Connect for live monitoring.

    Args:
        image_path (str): Path to the image file to upload
        token (str): Prusa Connect camera token
        fingerprint (str): Prusa Connect camera fingerprint
        rotation (int): Rotation angle to apply before upload (0, 90, 180, 270)
        timeout (int): Request timeout in seconds

    Returns:
        bool: True if upload was successful, False otherwise
    """
    if not token or not fingerprint:
        logger.error("Prusa Connect token and fingerprint required")
        return False

    try:
        # Read image data
        with open(image_path, "rb") as f:
            image_data = f.read()

        # Apply rotation if needed
        if rotation != 0:
            image_data = rotate_image_bytes(image_data, rotation)

        # Upload to Prusa Connect
        url = "https://webcam.connect.prusa3d.com/c/snapshot"
        headers = {
            "Accept": "text/plain",
            "Content-type": "image/jpg",
            "Fingerprint": fingerprint,
            "Token": token,
            "Content-length": str(len(image_data)),
        }

        # Log the upload operation (INFO level for visibility)
        logger.info(
            f"Uploading to Prusa Connect: {url} (size: {len(image_data)} bytes)"
        )

        response = requests.put(url, headers=headers, data=image_data, timeout=timeout)

        if response.status_code in [200, 204]:
            logger.info("Image uploaded to Prusa Connect successfully")
            return True
        else:
            logger.warning(
                f"Prusa Connect upload failed with status {response.status_code}"
            )
            return False

    except requests.exceptions.RequestException as e:
        logger.warning(f"Failed to upload to Prusa Connect: {e}")
        return False
    except Exception as e:
        logger.error(f"Error uploading to Prusa Connect: {e}")
        return False


# ============================================================================
# PrusaLink API
# ============================================================================


def get_job_info(printer_host, api_key, timeout=5):
    """
    Query the PrusaLink API for detailed job information.

    Args:
        printer_host (str): Printer hostname or IP address
        api_key (str): PrusaLink API key
        timeout (int): Request timeout in seconds

    Returns:
        dict: Job information including file details, or None if error
    """
    try:
        url = f"http://{printer_host}/api/v1/job"
        headers = {"X-Api-Key": api_key}
        response = requests.get(url, headers=headers, timeout=timeout)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.Timeout:
        logger.debug("Job info request timed out")
        return None
    except requests.exceptions.ConnectionError:
        logger.debug("Could not connect to printer for job info")
        return None
    except requests.exceptions.RequestException as e:
        logger.debug(f"Job info request failed: {e}")
        return None


def get_printer_status(printer_host, api_key, timeout=5):
    """
    Query the PrusaLink API for printer status.

    Args:
        printer_host (str): Printer hostname or IP address
        api_key (str): PrusaLink API key
        timeout (int): Request timeout in seconds

    Returns:
        dict: Printer status information, or None if error
    """
    try:
        url = f"http://{printer_host}/api/v1/status"
        headers = {"X-Api-Key": api_key}

        response = requests.get(url, headers=headers, timeout=timeout)
        response.raise_for_status()

        return response.json()

    except requests.exceptions.Timeout:
        logger.error(f"Request to {printer_host} timed out")
        return None
    except requests.exceptions.ConnectionError:
        logger.error(f"Cannot connect to printer at {printer_host}")
        return None
    except requests.exceptions.RequestException as e:
        logger.error(f"API request failed: {e}")
        return None


# ============================================================================
# System Validation
# ============================================================================


def check_command(cmd, name=None, timeout=15):
    """
    Check if a command exists and is executable.

    Args:
        cmd (str): Command to check
        name (str): Display name (defaults to cmd)
        timeout (int): Command timeout in seconds

    Returns:
        bool: True if command is available, False otherwise
    """
    if name is None:
        name = cmd

    try:
        result = subprocess.run(
            [cmd, "--version"], capture_output=True, text=True, timeout=timeout
        )
        # Some versions of ffmpeg return non-zero but still work
        if result.returncode == 0 or (result.stdout or result.stderr):
            logger.debug(f"✓ {name} is installed")
            return True
        else:
            logger.error(f"✗ {name} is not working properly")
            return False
    except FileNotFoundError:
        logger.error(f"✗ {name} is not installed")
        return False
    except subprocess.TimeoutExpired:
        logger.error(f"✗ {name} check timed out")
        return False
    except Exception as e:
        logger.error(f"✗ Error checking {name}: {e}")
        return False


def check_python_package(package, import_name=None):
    """
    Check if a Python package is installed.

    Args:
        package (str): Package name
        import_name (str): Import name if different from package name

    Returns:
        bool: True if package is installed, False otherwise
    """
    if import_name is None:
        import_name = package

    try:
        __import__(import_name)
        logger.debug(f"✓ Python package '{package}' is installed")
        return True
    except ImportError:
        logger.error(f"✗ Python package '{package}' is not installed")
        return False


def check_camera(timeout=10):
    """
    Check if camera is accessible via rpicam-still.

    Args:
        timeout (int): Command timeout in seconds

    Returns:
        bool: True if camera is detected, False otherwise
    """
    try:
        result = subprocess.run(
            ["rpicam-still", "--list-cameras"],
            capture_output=True,
            text=True,
            timeout=timeout,
        )

        if result.returncode == 0 and ("No cameras available" not in result.stderr):
            logger.info("✓ Camera detected and accessible")
            return True
        else:
            logger.error("✗ No camera detected")
            return False
    except FileNotFoundError:
        logger.error("✗ rpicam-still not found")
        return False
    except subprocess.TimeoutExpired:
        logger.error("✗ Camera check timed out")
        return False
    except Exception as e:
        logger.error(f"✗ Error checking camera: {e}")
        return False


def validate_env_config(env_vars):
    """
    Validate environment configuration variables.

    Args:
        env_vars (dict): Dictionary of environment variable names to values

    Returns:
        tuple: (bool, list) - (is_valid, list of missing/invalid variables)
    """
    missing = []

    for var_name, value in env_vars.items():
        if not value or (isinstance(value, str) and value.startswith("your_")):
            missing.append(var_name)

    return (len(missing) == 0, missing)


def validate_rotation(rotation):
    """
    Validate camera rotation value.

    Args:
        rotation: Rotation value to validate

    Returns:
        int: Valid rotation value (0, 90, 180, or 270), defaults to 0 if invalid
    """
    try:
        rotation = int(rotation)
        if rotation in [0, 90, 180, 270]:
            return rotation
        else:
            logger.warning(
                f"Invalid rotation {rotation}, must be 0/90/180/270. Using 0."
            )
            return 0
    except (ValueError, TypeError):
        logger.warning(f"Invalid rotation value '{rotation}'. Using 0.")
        return 0


# ============================================================================
# Email Operations
# ============================================================================


def send_email(
    smtp_server,
    smtp_port,
    email_from,
    email_to,
    subject,
    html_body,
    attachment_path=None,
    smtp_username=None,
    smtp_password=None,
):
    """
    Send an email with optional attachment.

    Args:
        smtp_server (str): SMTP server hostname
        smtp_port (int): SMTP server port
        email_from (str): Sender email address
        email_to (str): Recipient email address
        subject (str): Email subject
        html_body (str): HTML email body
        attachment_path (str, optional): Path to file to attach
        smtp_username (str, optional): SMTP username for authentication
        smtp_password (str, optional): SMTP password for authentication

    Returns:
        bool: True if email was sent successfully, False otherwise
    """
    try:
        import smtplib
        from email.mime.multipart import MIMEMultipart
        from email.mime.base import MIMEBase
        from email.mime.text import MIMEText
        from email import encoders

        msg = MIMEMultipart()
        msg["From"] = email_from
        msg["To"] = email_to
        msg["Subject"] = subject

        # Attach HTML body
        msg.attach(MIMEText(html_body, "html"))

        # Attach file if provided
        if attachment_path and os.path.exists(attachment_path):
            with open(attachment_path, "rb") as f:
                part = MIMEBase("application", "octet-stream")
                part.set_payload(f.read())
                encoders.encode_base64(part)
                filename = os.path.basename(attachment_path)
                part.add_header(
                    "Content-Disposition", f"attachment; filename={filename}"
                )
                msg.attach(part)

        # Send email
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            has_auth = bool(smtp_username and smtp_password)
            if has_auth:
                server.starttls()
                server.login(smtp_username, smtp_password)
            server.send_message(msg)

        logger.info(f"Email sent successfully to {email_to}")
        return True

    except Exception as e:
        logger.error(f"Failed to send email: {e}")
        return False
