import subprocess
import sys
from pathlib import Path

import pytest

_current_dir = Path(__file__).parent
_client_py_path = str(_current_dir / "client.py")
_config_path = str(_current_dir / "config.yaml")


def maybe_patch_args_with_debug(args: list[str]) -> list[str]:
    # Do a best effort to invoke the child with debugging.
    # This invokes internal methods from bundles provided by the IDE
    # and may not always work.
    try:
        from pydevd import (  # pyright:ignore[reportMissingImports] - provided by IDE
            _pydev_bundle,
        )

        return _pydev_bundle.pydev_monkey.patch_args(args)
    except Exception:
        return args


_skipped_tests_sync = [
    # Need to use async APIs for proper cancellation support in Python.
    "--skip",
    "Client Cancellation/HTTPVersion:1/Protocol:PROTOCOL_CONNECT/Codec:CODEC_PROTO/Compression:COMPRESSION_IDENTITY/TLS:false/unary/cancel-after-close-send",
]


def test_client_sync():
    args = maybe_patch_args_with_debug(
        [sys.executable, _client_py_path, "--mode", "sync"]
    )
    result = subprocess.run(
        [
            "go",
            "tool",
            "connectconformance",
            "--conf",
            _config_path,
            "--mode",
            "client",
            *_skipped_tests_sync,
            "--",
            *args,
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        pytest.fail(f"\n{result.stdout}\n{result.stderr}")


def test_client_async():
    args = maybe_patch_args_with_debug(
        [sys.executable, _client_py_path, "--mode", "async"]
    )
    result = subprocess.run(
        [
            "go",
            "tool",
            "connectconformance",
            "--conf",
            _config_path,
            "--mode",
            "client",
            "--",
            *args,
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        pytest.fail(f"\n{result.stdout}\n{result.stderr}")
