#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# Copyright 2024 Brian Warner
"""
Prusa 3D Printer Timelapse Monitor

This script monitors a Prusa 3D printer via the Prusa Link API,
automatically captures timelapse images during printing, and emails
the compiled video when the print completes.
"""

import os
import sys
import time
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from dotenv import load_dotenv
import logging

# Import shared library functions
import prusa_lib

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class PrusaTimelapse:
    """Main class for monitoring Prusa printer and creating timelapses."""

    def __init__(self):
        """Initialize the timelapse monitor with configuration from .env file."""
        load_dotenv()

        # PrusaLink API configuration
        self.printer_host = os.getenv("PRUSA_PRINTER_HOST")
        self.api_key = os.getenv("PRUSA_API_KEY")

        if not self.printer_host:
            raise ValueError("PRUSA_PRINTER_HOST must be set in .env file")
        if not self.api_key:
            raise ValueError("PRUSA_API_KEY must be set in .env file")

        self.api_base_url = f"http://{self.printer_host}/api/v1"

        # Camera configuration
        self.capture_interval = int(os.getenv("CAPTURE_INTERVAL_SECONDS", "30"))
        self.image_width = int(os.getenv("IMAGE_WIDTH", "1920"))
        self.image_height = int(os.getenv("IMAGE_HEIGHT", "1080"))

        # Camera rotation (0, 90, 180, 270 degrees)
        rotation_str = os.getenv("CAMERA_ROTATION", "0").strip()
        self.camera_rotation = prusa_lib.validate_rotation(rotation_str)

        # Focus distance and lens position calculation
        focus_distance = int(os.getenv("FOCUS_DISTANCE", "22"))
        if focus_distance < 10 or focus_distance > 100:
            logger.warning(
                f"Invalid FOCUS_DISTANCE {focus_distance}, using default 22cm"
            )
            focus_distance = 22
        self.focus_distance = focus_distance
        self.lens_position = round(100 / focus_distance, 2)
        logger.info(
            f"Focus distance: {focus_distance}cm (lens position: {self.lens_position})"
        )

        # Storage configuration
        home_dir = Path.home()
        prints_dir_name = os.getenv("PRINTS_DIR_NAME", "prints").strip()
        if not prints_dir_name:
            raise ValueError("PRINTS_DIR_NAME cannot be empty")
        self.prints_dir = home_dir / prints_dir_name
        self.prints_dir.mkdir(exist_ok=True)

        # Camera extra parameters (sanitized)
        self.rpicam_extra_params = prusa_lib.sanitize_rpicam_params(
            os.getenv("RPICAM_EXTRA_PARAMS", "").strip()
        )

        # Email configuration
        self.smtp_server = os.getenv("SMTP_SERVER")
        self.smtp_port = int(os.getenv("SMTP_PORT", "587"))
        self.smtp_username = os.getenv("SMTP_USERNAME")
        self.smtp_password = os.getenv("SMTP_PASSWORD")
        self.email_from = os.getenv("EMAIL_FROM", self.smtp_username)
        self.email_to = os.getenv("EMAIL_TO")

        # Video encoding configuration
        self.video_fps = int(os.getenv("VIDEO_FPS", "30"))
        # CRF value (lower = better quality)
        self.video_quality = int(os.getenv("VIDEO_QUALITY", "23"))
        # Batch size for memory-efficient video processing (frames per batch)
        self.video_batch_size = int(os.getenv("VIDEO_BATCH_SIZE", "150"))

        # Polling configuration
        self.poll_interval = int(os.getenv("POLL_INTERVAL_SECONDS", "10"))

        # Prusa Connect camera configuration (optional - for live monitoring)
        self.prusa_connect_camera_token = os.getenv("PRUSA_CONNECT_CAMERA_TOKEN")
        self.prusa_connect_camera_fingerprint = os.getenv(
            "PRUSA_CONNECT_CAMERA_FINGERPRINT"
        )
        self.prusa_connect_url = "https://webcam.connect.prusa3d.com/c/snapshot"

        # Enable Prusa Connect uploads if both token and fingerprint are provided
        self.enable_prusa_connect_upload = bool(
            self.prusa_connect_camera_token and self.prusa_connect_camera_fingerprint
        )

        if self.enable_prusa_connect_upload:
            logger.info("Prusa Connect camera uploads: ENABLED")
        else:
            logger.info(
                "Prusa Connect camera uploads: DISABLED (set PRUSA_CONNECT_CAMERA_TOKEN and "
                "PRUSA_CONNECT_CAMERA_FINGERPRINT to enable)"
            )

        # State tracking
        self.current_print_name = None
        self.current_print_start = None
        self.current_job_metadata = None
        self.image_sequence = []
        self.is_printing = False
        self.connection_errors = 0  # Track consecutive connection errors

        self._validate_config()

    def _validate_config(self):
        """Validate that required configuration is present."""
        required_vars = {
            "PRUSA_PRINTER_HOST": self.printer_host,
            "PRUSA_API_KEY": self.api_key,
        }

        missing = [key for key, value in required_vars.items() if not value]
        if missing:
            raise ValueError(
                f"Missing required environment variables: {', '.join(missing)}"
            )

        # Check if email is configured (both EMAIL_TO and SMTP_SERVER required)
        if self.email_to or self.smtp_server:
            if not (self.email_to and self.smtp_server):
                raise ValueError(
                    "Email configuration incomplete: both EMAIL_TO and SMTP_SERVER "
                    "must be provided together, or both left empty to disable email notifications"
                )

        # Check if authentication credentials are provided together or not at all
        has_username = bool(self.smtp_username)
        has_password = bool(self.smtp_password)
        if has_username != has_password:
            raise ValueError(
                "Both SMTP_USERNAME and SMTP_PASSWORD must be provided together, "
                "or both left empty for no authentication"
            )

        if self.is_email_configured():
            logger.info("Configuration validated successfully (email enabled)")
        else:
            logger.info("Configuration validated successfully (email disabled)")

    def is_email_configured(self):
        """Check if email notifications are configured.

        Returns:
            bool: True if both EMAIL_TO and SMTP_SERVER are configured, False otherwise
        """
        return bool(self.email_to and self.smtp_server)

    def reload_env_config(self):
        """
        Reload configuration from .env file at runtime.

        Only reloads safe parameters that can change during operation.
        Critical settings like API keys and printer host are not reloaded.

        Returns:
            bool: True if configuration was reloaded successfully
        """
        try:
            # Reload .env file
            load_dotenv(override=True)

            # Track what changed for logging
            changes = []

            # Reload capture interval
            new_capture_interval = int(os.getenv("CAPTURE_INTERVAL_SECONDS", "30"))
            if new_capture_interval != self.capture_interval:
                changes.append(
                    f"CAPTURE_INTERVAL_SECONDS: {self.capture_interval}s → {new_capture_interval}s"
                )
                self.capture_interval = new_capture_interval

            # Reload poll interval
            new_poll_interval = int(os.getenv("POLL_INTERVAL_SECONDS", "10"))
            if new_poll_interval != self.poll_interval:
                changes.append(
                    f"POLL_INTERVAL_SECONDS: {self.poll_interval}s → {new_poll_interval}s"
                )
                self.poll_interval = new_poll_interval

            # Reload video settings
            new_video_fps = int(os.getenv("VIDEO_FPS", "30"))
            if new_video_fps != self.video_fps:
                changes.append(f"VIDEO_FPS: {self.video_fps} → {new_video_fps}")
                self.video_fps = new_video_fps

            new_video_quality = int(os.getenv("VIDEO_QUALITY", "23"))
            if new_video_quality != self.video_quality:
                changes.append(
                    f"VIDEO_QUALITY: {self.video_quality} → {new_video_quality}"
                )
                self.video_quality = new_video_quality

            new_video_batch_size = int(os.getenv("VIDEO_BATCH_SIZE", "150"))
            if new_video_batch_size != self.video_batch_size:
                changes.append(
                    f"VIDEO_BATCH_SIZE: {self.video_batch_size} → {new_video_batch_size}"
                )
                self.video_batch_size = new_video_batch_size

            # Reload camera rotation
            rotation_str = os.getenv("CAMERA_ROTATION", "0").strip()
            new_rotation = prusa_lib.validate_rotation(rotation_str)
            if new_rotation != self.camera_rotation:
                changes.append(
                    f"CAMERA_ROTATION: {self.camera_rotation}° → {new_rotation}°"
                )
                self.camera_rotation = new_rotation

            # Reload focus distance and recalculate lens position
            new_focus_distance = int(os.getenv("FOCUS_DISTANCE", "22"))
            if new_focus_distance < 10 or new_focus_distance > 100:
                logger.warning(
                    f"Invalid FOCUS_DISTANCE {new_focus_distance}, using current value"
                )
                new_focus_distance = self.focus_distance
            if new_focus_distance != self.focus_distance:
                new_lens_position = round(100 / new_focus_distance, 2)
                changes.append(
                    f"FOCUS_DISTANCE: {self.focus_distance}cm → {new_focus_distance}cm (lens "
                    f"position: {self.lens_position} → {new_lens_position})"
                )
                self.focus_distance = new_focus_distance
                self.lens_position = new_lens_position

            # Reload camera parameters
            new_rpicam_params = prusa_lib.sanitize_rpicam_params(
                os.getenv("RPICAM_EXTRA_PARAMS", "").strip()
            )
            if new_rpicam_params != self.rpicam_extra_params:
                changes.append(
                    f"RPICAM_EXTRA_PARAMS: '{self.rpicam_extra_params}' → '{new_rpicam_params}'"
                )
                self.rpicam_extra_params = new_rpicam_params

            # Log changes if any
            if changes:
                logger.info("Configuration reloaded with changes:")
                for change in changes:
                    logger.info(f"  - {change}")

            return True

        except Exception as e:
            logger.warning(f"Failed to reload configuration: {e}")
            return False

    def get_printer_status(self):
        """
        Query the PrusaLink API for printer status.

        Returns:
            dict: Printer status information including state and job details
        """
        status = prusa_lib.get_printer_status(
            self.printer_host, self.api_key, timeout=20
        )

        if status:
            # Reset error counter on success
            if self.connection_errors > 0:
                logger.info("Printer connection restored")
                self.connection_errors = 0
        else:
            self.connection_errors += 1
            # Only log first few errors to avoid log spam
            if self.connection_errors <= 3:
                logger.debug(
                    f"Printer connection issue (#{self.connection_errors}) - will retry"
                )
            elif self.connection_errors == 4:
                logger.warning(
                    "Printer connection unstable - will continue retrying silently"
                )

        return status

    def is_printer_printing(self, status):
        """
        Determine if the printer is currently printing.

        Args:
            status (dict): Printer status dictionary

        Returns:
            bool: True if printer is printing, False otherwise
        """
        if not status:
            return False

        # PrusaLink status has 'printer' key with 'state'
        # Valid printing states: PRINTING, PAUSED
        printer_state = status.get("printer", {}).get("state", "").upper()
        return printer_state in ["PRINTING", "PAUSED"]

    def get_job_name(self, job_info):
        """
        Extract the current job/print name from job information.

        Args:
            job_info (dict): Job information dictionary from /api/v1/job endpoint

        Returns:
            str: Job name or 'unknown' if not available
        """
        if not job_info:
            return "unknown"

        # PrusaLink /api/v1/job has 'file' key with 'display_name' or 'name'
        file_info = job_info.get("file", {})
        name = file_info.get("display_name") or file_info.get(
            "name", "unknown"
        )  # noqa: W503

        # Clean up the name (remove path and extension)
        if name and name != "unknown":
            name = Path(name).stem

        return name

    def upload_to_prusa_connect(self, image_path):
        """
        Upload an image to Prusa Connect for live monitoring.

        Args:
            image_path (str): Path to the image file to upload

        Returns:
            bool: True if upload was successful, False otherwise
        """
        if not self.enable_prusa_connect_upload:
            return True  # Not enabled, skip silently

        return prusa_lib.upload_to_prusa_connect(
            image_path,
            self.prusa_connect_camera_token,
            self.prusa_connect_camera_fingerprint,
            rotation=self.camera_rotation,
        )

    def capture_image(self, output_path):
        """
        Capture an image using rpicam-still.

        Args:
            output_path (str): Path where image should be saved

        Returns:
            bool: True if capture was successful, False otherwise
        """
        success = prusa_lib.capture_image(
            output_path,
            width=self.image_width,
            height=self.image_height,
            extra_params=self.rpicam_extra_params,
            lens_position=self.lens_position,
        )

        if success:
            # Upload to Prusa Connect if enabled (non-blocking - doesn't affect timelapse)
            if self.enable_prusa_connect_upload:
                self.upload_to_prusa_connect(output_path)

        return success

    def create_video(self, image_dir, output_video):
        """
        Create a timelapse video from image sequence using ffmpeg.

        Args:
            image_dir (Path): Directory containing image sequence
            output_video (str): Path for output video file

        Returns:
            bool: True if video creation was successful, False otherwise
        """
        logger.info(f"Creating video from {len(self.image_sequence)} images...")

        return prusa_lib.create_video(
            image_dir,
            output_video,
            fps=self.video_fps,
            quality=self.video_quality,
            rotation=self.camera_rotation,
            batch_size=self.video_batch_size,
        )

    def _build_email_body(self, print_name, print_duration, job_metadata=None):
        """
        Build a detailed HTML email body with job information.

        Args:
            print_name (str): Name of the print job
            print_duration (float): Actual print duration in seconds
            job_metadata (dict): Job metadata from API

        Returns:
            str: Formatted HTML email body
        """
        # Format duration
        hours = int(print_duration // 3600)
        minutes = int((print_duration % 3600) // 60)
        duration_str = f"{hours}h {minutes}m"

        # Start building HTML email
        html = f"""
<!DOCTYPE html>
<html>
<head>
    <style>
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 800px;
            margin: 0 auto;
            padding: 20px;
            background-color: #f5f5f5;
        }}
        .container {{
            background-color: white;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            overflow: hidden;
        }}
        .header {{
            background: linear-gradient(135deg, #FF6B35 0%, #F7931E 100%);
            color: white;
            padding: 30px;
            text-align: center;
        }}
        .header h1 {{
            margin: 0;
            font-size: 28px;
        }}
        .header .emoji {{
            font-size: 36px;
            margin: 10px 0;
        }}
        .content {{
            padding: 30px;
        }}
        .section {{
            margin-bottom: 30px;
        }}
        .section-title {{
            font-size: 20px;
            color: #FF6B35;
            border-bottom: 2px solid #FF6B35;
            padding-bottom: 8px;
            margin-bottom: 15px;
            font-weight: bold;
        }}
        .info-grid {{
            display: table;
            width: 100%;
            border-collapse: collapse;
        }}
        .info-row {{
            display: table-row;
        }}
        .info-row:nth-child(even) {{
            background-color: #f9f9f9;
        }}
        .info-label {{
            display: table-cell;
            padding: 10px;
            font-weight: 600;
            color: #555;
            width: 200px;
        }}
        .info-value {{
            display: table-cell;
            padding: 10px;
            color: #333;
        }}
        .highlight {{
            background-color: #FFF3E0;
            padding: 15px;
            border-left: 4px solid #FF6B35;
            margin: 15px 0;
        }}
        .footer {{
            background-color: #f9f9f9;
            padding: 20px;
            text-align: center;
            color: #666;
            font-size: 14px;
            border-top: 1px solid #ddd;
        }}
        .settings-table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 10px;
        }}
        .settings-table td {{
            padding: 8px;
            border-bottom: 1px solid #eee;
        }}
        .settings-table td:first-child {{
            font-weight: 600;
            color: #555;
            width: 250px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Your print is done! 🎉</h1>
        </div>
        <div class="content">
            <div class="section">
                <div class="section-title">Print Summary</div>
                <div class="info-grid">
                    <div class="info-row">
                        <div class="info-label">File Name</div>
                        <div class="info-value"><strong>{print_name}</strong></div>
                    </div>
                    <div class="info-row">
                        <div class="info-label">Start Time</div>
                        <div class="info-value">
                            {self.current_print_start.strftime('%Y-%m-%d %H:%M:%S')}
                        </div>
                    </div>
                    <div class="info-row">
                        <div class="info-label">Completed</div>
                        <div class="info-value">{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</div>
                    </div>
                    <div class="info-row">
                        <div class="info-label">Duration</div>
                        <div class="info-value"><strong>{duration_str}</strong></div>
                    </div>
"""

        # Extract detailed information from job metadata if available
        if job_metadata:
            job = job_metadata.get("job", {})
            file_info = job.get("file", {})
            meta = file_info.get("meta", {})

            # File size
            file_size = file_info.get("size")
            if file_size:
                size_mb = file_size / (1024 * 1024)
                html += f"""
                    <div class="info-row">
                        <div class="info-label">File Size</div>
                        <div class="info-value">{size_mb:.2f} MB</div>
                    </div>
"""

            # Filament information
            filament_type = meta.get("filament_type")
            if filament_type:
                html += f"""
                    <div class="info-row">
                        <div class="info-label">Filament Type</div>
                        <div class="info-value">{filament_type}</div>
                    </div>
"""

            filament_used_g = meta.get("filament used [g]")
            filament_used_mm = meta.get("filament used [mm]")
            if filament_used_g:
                usage_str = f"{filament_used_g:.2f}g"
                if filament_used_mm:
                    usage_str += f" ({filament_used_mm:.2f}mm)"
                html += f"""
                    <div class="info-row">
                        <div class="info-label">Filament Used</div>
                        <div class="info-value">{usage_str}</div>
                    </div>
"""

            # Layer information
            layer_height = meta.get("layer_height")
            if layer_height:
                html += f"""
                    <div class="info-row">
                        <div class="info-label">Layer Height</div>
                        <div class="info-value">{layer_height}mm</div>
                    </div>
"""

            # Temperature information
            temp_nozzle = meta.get("temperature")
            temp_bed = meta.get("bed_temperature")
            if temp_nozzle:
                html += f"""
                    <div class="info-row">
                        <div class="info-label">Nozzle Temperature</div>
                        <div class="info-value">{temp_nozzle}°C</div>
                    </div>
"""
            if temp_bed:
                html += f"""
                    <div class="info-row">
                        <div class="info-label">Bed Temperature</div>
                        <div class="info-value">{temp_bed}°C</div>
                    </div>
"""

            # Close info grid
            html += """
                </div>
            </div>
"""

            # Estimated vs actual time
            estimated_time = meta.get(
                "estimated printing time (normal mode)"
            ) or meta.get("estimated_print_time")
            if estimated_time and isinstance(estimated_time, int):
                # Convert seconds to readable format
                est_hours = int(estimated_time // 3600)
                est_minutes = int((estimated_time % 3600) // 60)
                estimated_str = f"{est_hours}h {est_minutes}m"

                # Calculate time difference
                diff_seconds = print_duration - estimated_time
                diff_minutes = int(abs(diff_seconds) // 60)
                diff_sign = "+" if diff_seconds > 0 else "-"
                diff_color = "#d32f2f" if diff_seconds > 0 else "#388e3c"

                html += f"""
            <div class="highlight">
                <strong>Time Comparison:</strong><br>
                Estimated: {estimated_str} | Actual: {duration_str}
                <span style="color: {diff_color}; font-weight: bold;">
                    ({diff_sign}{diff_minutes} min)
                </span>
            </div>
"""

            # Slicer settings section
            if meta:
                html += """
            <div class="section">
                <div class="section-title">Slicer Settings</div>
                <table class="settings-table">
"""

                # Organize settings by category
                important_settings = [
                    ("nozzle_diameter", "Nozzle Diameter"),
                    ("fill_density", "Infill Density"),
                    ("support_material", "Support Material"),
                    ("brim_width", "Brim Width"),
                    ("ironing", "Ironing"),
                ]

                for key, label in important_settings:
                    value = meta.get(key)
                    if value is not None:
                        html += f"""
                    <tr>
                        <td>{label}</td>
                        <td>{value}</td>
                    </tr>
"""

                # Add any other settings not in the important list
                displayed_keys = set(k for k, _ in important_settings)
                displayed_keys.update(
                    [
                        "filament_type",
                        "filament used [g]",
                        "filament used [mm]",
                        "layer_height",
                        "temperature",
                        "bed_temperature",
                        "estimated printing time (normal mode)",
                        "estimated_print_time",
                        "file_type",
                        "thumbnail",
                        "display_name",
                        "name",
                    ]
                )

                other_settings = {
                    k: v for k, v in meta.items() if k not in displayed_keys
                }
                if other_settings:
                    count = 0
                    for key, value in sorted(other_settings.items()):
                        if count >= 15:
                            break
                        # Format key nicely
                        display_key = key.replace("_", " ").title()
                        html += f"""
                    <tr>
                        <td>{display_key}</td>
                        <td>{value}</td>
                    </tr>
"""
                        count += 1

                    if len(other_settings) > 15:
                        html += f"""
                    <tr>
                    <td colspan="2" style="text-align: center; color: #999; font-style: italic;">
                        ... and {len(other_settings) - 15} more settings
                    </td>
                    </tr>
"""

                html += """
                </table>
            </div>
"""
        else:
            # Close info grid if no metadata
            html += """
                </div>
            </div>
"""

        # Footer
        html += """
        </div>
        <div class="footer">
            <p style="margin-top: 15px; font-size: 12px;">
                <a href="https://github.com/brianwarner/timelapse-for-prusa" target="_blank"
                style="color: #999; text-decoration: none;">Timelapse for Prusa</a>
            </p>
        </div>
    </div>
</body>
</html>
"""

        return html

    def send_email(self, video_path, print_name, print_duration, job_metadata=None):
        """
        Send an email with the timelapse video attached and detailed job summary.

        If email is not configured, this method will return without sending.

        Args:
            video_path (str): Path to the video file
            print_name (str): Name of the print job
            print_duration (float): Duration of print in seconds
            job_metadata (dict): Job metadata from API (captured at print start)
        """
        # Skip if email is not configured
        if not self.is_email_configured():
            logger.info("Email not configured - skipping notification")
            return

        try:
            # Build detailed job summary (HTML)
            body = self._build_email_body(print_name, print_duration, job_metadata)

            file_size_mb = os.path.getsize(video_path) / (1024 * 1024)
            logger.info(f"Sending email with video ({file_size_mb:.2f} MB)...")

            success = prusa_lib.send_email(
                smtp_server=self.smtp_server,
                smtp_port=self.smtp_port,
                email_from=self.email_from,
                email_to=self.email_to,
                subject=f"Print Complete: {print_name}",
                html_body=body,
                attachment_path=video_path,
                smtp_username=self.smtp_username,
                smtp_password=self.smtp_password,
            )

            if success:
                logger.info("Email sent successfully!")
            else:
                logger.error("Failed to send email")

        except Exception as e:
            logger.error(f"Error sending email: {e}")

    def cleanup_images(self, image_dir):
        """
        Delete image files after video creation.

        Args:
            image_dir (Path): Directory containing images to delete
        """
        try:
            for image_path in image_dir.glob("frame_*.jpg"):
                image_path.unlink()
            logger.info("Cleaned up image files")
        except Exception as e:
            logger.error(f"Error cleaning up images: {e}")

    def _write_print_log(self, log_path, print_name, duration_seconds):
        """
        Write a log file with print details.

        Args:
            log_path (Path): Path to the log file
            print_name (str): Name of the print
            duration_seconds (float): Duration in seconds
        """
        end_time = datetime.now()
        start_time = end_time - timedelta(seconds=duration_seconds)

        hours = int(duration_seconds // 3600)
        minutes = int((duration_seconds % 3600) // 60)

        with open(log_path, "w") as f:
            f.write("Prusa Timelapse Print Log\n")
            f.write("=" * 50 + "\n\n")
            f.write(f"File Name: {print_name}\n")
            f.write(f"Start Time: {start_time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"End Time: {end_time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Duration: {hours}h {minutes}m\n")
            f.write(f"Frames Captured: {len(self.image_sequence)}\n")
            f.write(f"Capture Interval: {self.capture_interval} seconds\n")

            if self.current_job_metadata:
                f.write("\n" + "=" * 50 + "\n")
                f.write("Job Metadata\n")
                f.write("=" * 50 + "\n\n")

                # Add file information
                file_info = self.current_job_metadata.get("file", {})
                if file_info:
                    f.write(f"Display Name: {file_info.get('display_name', 'N/A')}\n")
                    f.write(f"File Name: {file_info.get('name', 'N/A')}\n")
                    f.write(f"File Path: {file_info.get('path', 'N/A')}\n")
                    size_bytes = file_info.get("size", 0)
                    if size_bytes:
                        size_mb = size_bytes / (1024 * 1024)
                        f.write(f"File Size: {size_mb:.2f} MB\n")

    def handle_print_start(self, print_name, job_status=None):
        """
        Handle the start of a new print job.

        Args:
            print_name (str): Name of the print job
            job_status (dict): Full job status from API for metadata
        """
        self.current_print_name = print_name
        self.current_print_start = datetime.now()
        self.current_job_metadata = job_status
        self.image_sequence = []
        self.is_printing = True

        logger.info(f"Print started: {print_name}")

    def handle_print_end(self):
        """Handle the end of a print job."""
        if not self.current_print_name or not self.image_sequence:
            logger.warning("Print ended but no images were captured")
            self.is_printing = False
            return

        logger.info(f"Print '{self.current_print_name}' completed")
        logger.info(f"Captured {len(self.image_sequence)} images")

        # Calculate print duration
        print_duration = (
            datetime.now() - self.current_print_start
        ).total_seconds()  # noqa: W503

        # Get the image directory (parent of first image)
        image_dir = Path(self.image_sequence[0]).parent

        # Create video in the prints directory (parent of image_dir)
        video_filename = f"{image_dir.name}.mp4"
        video_path = self.prints_dir / video_filename

        logger.info(f"Creating timelapse video: {video_path}")
        if self.create_video(image_dir, video_path):
            logger.info("Video created successfully")

            # Create log file
            log_filename = f"{image_dir.name}.log"
            log_path = self.prints_dir / log_filename
            try:
                self._write_print_log(log_path, self.current_print_name, print_duration)
                logger.info(f"Print log created: {log_path}")
            except Exception as e:
                logger.error(f"Failed to create log file: {e}")

            # Send email notification if configured
            if self.is_email_configured():
                logger.info("Sending email notification")
                self.send_email(
                    video_path,
                    self.current_print_name,
                    print_duration,
                    self.current_job_metadata,
                )
            else:
                logger.info(
                    "Email not configured - timelapse saved to: {}".format(video_path)
                )

            # Delete the entire capture directory (images already in video)
            logger.info(f"Removing capture directory: {image_dir}")
            try:
                shutil.rmtree(image_dir)
                logger.info("Capture directory removed")
            except Exception as e:
                logger.error(f"Failed to remove capture directory: {e}")
        else:
            logger.error("Failed to create video")

        # Reset state
        self.is_printing = False
        self.current_print_name = None
        self.current_print_start = None
        self.current_job_metadata = None
        self.image_sequence = []

    def capture_timelapse_frame(self):
        """Capture a single timelapse frame."""
        if not self.is_printing:
            return

        # Generate filename
        timestamp = self.current_print_start.strftime("%Y-%m-%d-%H-%M")
        safe_print_name = "".join(
            c for c in self.current_print_name if c.isalnum() or c in ("-", "_")
        )
        filename_base = f"{timestamp}_{safe_print_name}"

        # Create subdirectory for this print
        print_dir = self.prints_dir / filename_base
        print_dir.mkdir(exist_ok=True)

        # Frame filename with sequence number
        frame_num = len(self.image_sequence)
        frame_path = print_dir / f"frame_{frame_num:05d}.jpg"

        # Capture image
        if self.capture_image(str(frame_path)):
            self.image_sequence.append(str(frame_path))

    def run(self):
        """Main monitoring loop."""
        logger.info("Starting Timelapse for Prusa...")
        logger.info(f"Prints directory: {self.prints_dir}")
        logger.info(f"Polling interval: {self.poll_interval}s")
        logger.info(f"Capture interval: {self.capture_interval}s")

        last_capture_time = 0
        was_printing = False

        try:
            while True:
                # Reload configuration from .env at the start of each loop iteration
                self.reload_env_config()

                # Get printer status
                status = self.get_printer_status()

                if status:
                    is_printing = self.is_printer_printing(status)

                    # Detect print start
                    if is_printing and not was_printing:
                        # Fetch detailed job information to get the file name
                        job_info = prusa_lib.get_job_info(
                            self.printer_host, self.api_key, timeout=10
                        )
                        print_name = self.get_job_name(job_info)
                        self.handle_print_start(print_name, job_info)

                    # Detect print end
                    elif not is_printing and was_printing:
                        self.handle_print_end()

                    # Capture frames during printing
                    if is_printing:
                        current_time = time.time()
                        if current_time - last_capture_time >= self.capture_interval:
                            self.capture_timelapse_frame()
                            last_capture_time = current_time

                    was_printing = is_printing

                # Wait before next poll
                time.sleep(self.poll_interval)

        except KeyboardInterrupt:
            logger.info("Shutting down...")
            # If printing when interrupted, save what we have
            if self.is_printing:
                logger.info("Saving current print timelapse...")
                self.handle_print_end()
        except Exception as e:
            logger.error(f"Unexpected error: {e}", exc_info=True)
            sys.exit(1)


def main():
    """Entry point for the script."""
    try:
        monitor = PrusaTimelapse()
        monitor.run()
    except ValueError as e:
        logger.error(f"Configuration error: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
