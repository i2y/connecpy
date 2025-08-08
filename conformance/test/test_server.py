import subprocess
import sys
from pathlib import Path

import pytest
from _util import maybe_patch_args_with_debug

_current_dir = Path(__file__).parent
_server_py_path = str(_current_dir / "server.py")
_config_path = str(_current_dir / "config.yaml")


_skipped_tests_sync = [
    # TODO: Implement server side of streaming for sync
    "--skip",
    "**/bidi-stream/**",
    "--skip",
    "**/client-stream/**",
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
            *_skipped_tests_sync,
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


_skipped_tests_async = [
    "--skip",
    # There seems to be a hypercorn bug with HTTP/1 and request termination.
    # https://github.com/pgjones/hypercorn/issues/314
    # TODO: We should probably test HTTP/1 with uvicorn to both increase coverage
    # of app servers and to verify behavior with the the dominant HTTP/1 ASGI server.
    "Server Message Size/HTTPVersion:1/**",
]


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
            *_skipped_tests_async,
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
