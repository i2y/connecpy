import subprocess
import sys
from pathlib import Path

import pytest
from _util import maybe_patch_args_with_debug

_current_dir = Path(__file__).parent
_server_py_path = str(_current_dir / "server.py")
_config_path = str(_current_dir / "config.yaml")


_skipped_tests_sync = [
    # TODO: While Hypercorn supports HTTP/2 and WSGI, its WSGI support is a very simple wrapper
    # that reads the entire request body before running the application, which does not work for
    # full duplex. There are no other popular WSGI servers that support HTTP/2, so in practice
    # it cannot be supported. It is possible in theory following hyper-h2's example code in
    # https://python-hyper.org/projects/hyper-h2/en/stable/wsgi-example.html though.
    "--skip",
    "**/bidi-stream/full-duplex/**",
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
