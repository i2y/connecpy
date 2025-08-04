import subprocess
import sys
from pathlib import Path

import pytest
from _util import maybe_patch_args_with_debug

_current_dir = Path(__file__).parent
_server_py_path = str(_current_dir / "server.py")
_config_path = str(_current_dir / "config.yaml")


_skipped_tests = [
    # TODO: Implement server side of streaming
    "--skip",
    "**/server-stream/**",
    "--skip",
    "**/unexpected-compressed-message",
]


def test_server_sync():
    args = maybe_patch_args_with_debug(
        [sys.executable, _server_py_path, "--mode", "sync"]
    )
    result = subprocess.run(
        [
            "go",
            "tool",
            "connectconformance",
            "--conf",
            _config_path,
            "--mode",
            "server",
            *_skipped_tests,
            "--parallel",
            "1",
            "--",
            *args,
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        pytest.fail(f"\n{result.stdout}\n{result.stderr}")


def test_server_async():
    args = maybe_patch_args_with_debug(
        [sys.executable, _server_py_path, "--mode", "async"]
    )
    result = subprocess.run(
        [
            "go",
            "tool",
            "connectconformance",
            "--conf",
            _config_path,
            "--mode",
            "server",
            *_skipped_tests,
            "--parallel",
            "1",
            "--",
            *args,
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        pytest.fail(f"\n{result.stdout}\n{result.stderr}")
