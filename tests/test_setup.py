"""Exercise the setup snapshot workflow without camera hardware or SMTP."""

import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys

from PIL import Image
import pytest


@pytest.fixture
def snapshot_setup(tmp_path):
    """Run the real setup script with capture and email replaced locally."""
    project_dir = Path(__file__).resolve().parents[1]
    shutil.copyfile(project_dir / "setup.sh", tmp_path / "setup.sh")
    library = (project_dir / "prusa_lib.py").read_text()
    library += '''

def capture_image(output_path, *args):
    if os.getenv("TEST_SNAPSHOT_FAILURE") == "capture":
        return False
    if os.getenv("TEST_SNAPSHOT_FAILURE") == "rotation":
        Path(output_path).write_bytes(b"invalid image")
        return True
    image = Image.new("RGB", (80, 40))
    image.paste((255, 0, 0), (0, 0, 40, 20))
    image.paste((0, 255, 0), (40, 0, 80, 20))
    image.paste((0, 0, 255), (0, 20, 40, 40))
    image.paste((255, 255, 0), (40, 20, 80, 40))
    image.save(output_path)
    return True

def send_email(**kwargs):
    attachment = Path(kwargs["attachment_path"]).read_bytes()
    (Path(__file__).parent / "emailed.jpg").write_bytes(attachment)
    return True
'''
    (tmp_path / "prusa_lib.py").write_text(library)
    capture_dir = Path("/tmp") / f"camera_snapshot_{tmp_path.name}"

    def run_setup(rotation, failure=""):
        config = "SMTP_SERVER=example.invalid\nEMAIL_TO=test@example.invalid\n"
        if rotation is not None:
            config += f"CAMERA_ROTATION={shlex.quote(rotation)}\n"
        (tmp_path / ".env").write_text(config)
        env = os.environ.copy()
        env.update(
            PATH=f"{Path(sys.executable).parent}{os.pathsep}{env['PATH']}",
            TERM="xterm",
            TEST_SNAPSHOT_ID=tmp_path.name,
            TEST_SNAPSHOT_FAILURE=failure,
        )
        env.pop("CAMERA_ROTATION", None)
        return subprocess.run(
            [
                "bash",
                "-c",
                'date() { printf "%s" "$TEST_SNAPSHOT_ID"; }; source "$0"',
                str(tmp_path / "setup.sh"),
            ],
            input="6\ny\n\n0\n",
            capture_output=True,
            text=True,
            env=env,
            timeout=20,
        )

    yield run_setup, tmp_path / "emailed.jpg", capture_dir
    shutil.rmtree(capture_dir, ignore_errors=True)


@pytest.mark.parametrize(
    "rotation, size, color",
    [
        ("0", (80, 40), (255, 0, 0)),
        ("90", (40, 80), (0, 0, 255)),
        ("180", (80, 40), (255, 255, 0)),
        ("270", (40, 80), (0, 255, 0)),
        (None, (80, 40), (255, 0, 0)),
        ("", (80, 40), (255, 0, 0)),
        ("invalid", (80, 40), (255, 0, 0)),
    ],
)
def test_snapshot_email_orientation(snapshot_setup, rotation, size, color):
    """Check the actual attachment's dimensions and direction of rotation."""
    run_setup, attachment, capture_dir = snapshot_setup
    result = run_setup(rotation)

    assert result.returncode == 0, result.stdout + result.stderr
    with Image.open(attachment) as image:
        assert image.size == size
        pixel = image.getpixel((image.width // 4, image.height // 4))
        assert all(abs(actual - expected) < 20 for actual, expected in zip(pixel, color))
    assert not capture_dir.exists()


@pytest.mark.parametrize("failure", ["capture", "rotation"])
def test_snapshot_failure_prevents_email(snapshot_setup, failure):
    """A failed capture or rotation must clean up and prevent sending."""
    run_setup, attachment, capture_dir = snapshot_setup
    result = run_setup("90", failure)

    assert result.returncode != 0
    assert "Failed to capture or rotate image" in result.stdout
    assert not attachment.exists()
    assert not capture_dir.exists()
