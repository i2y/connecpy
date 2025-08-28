"""Test for the generated Transport API code (requires transport_api=true in code generation)."""

import subprocess
import sys
import tempfile
from pathlib import Path

import pytest


@pytest.mark.skipif(
    sys.platform == "win32", reason="Test uses Unix-specific protoc invocation"
)
def test_generated_transport_api():
    """Test that generated Transport API code works correctly."""

    # Create a minimal proto file for testing
    proto_content = """
syntax = "proto3";
package test;

message Request {
    string data = 1;
}

message Response {
    string result = 1;
}

service TestService {
    rpc TestMethod(Request) returns (Response);
}
"""

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)

        # Write proto file
        proto_file = tmpdir_path / "test.proto"
        proto_file.write_text(proto_content)

        # Build the plugin first
        plugin_dir = Path(__file__).parent.parent.parent / "protoc-gen-connecpy"
        build_result = subprocess.run(
            ["go", "build", "-o", str(tmpdir_path / "protoc-gen-connecpy")],
            check=False,
            cwd=plugin_dir,
            capture_output=True,
            text=True,
        )

        if build_result.returncode != 0:
            pytest.skip(f"Failed to build plugin: {build_result.stderr}")

        # Generate code with Transport API enabled
        result = subprocess.run(
            [
                "protoc",
                f"--plugin=protoc-gen-connecpy={tmpdir_path / 'protoc-gen-connecpy'}",
                f"--connecpy_out=transport_api=true:{tmpdir}",
                f"--python_out={tmpdir}",
                f"-I{tmpdir}",
                str(proto_file),
            ],
            check=False,
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            pytest.skip(f"protoc failed: {result.stderr}")

        # Check that generated file contains Transport API code
        generated_file = tmpdir_path / "test_connecpy.py"
        assert generated_file.exists(), "Generated file not found"

        content = generated_file.read_text()

        # Check for Transport API specific code
        assert "class TestServiceClientProtocol(Protocol):" in content
        assert "class TestServiceClientSyncProtocol(Protocol):" in content
        assert "def create_client(" in content
        assert "def create_client_sync(" in content
        assert (
            "from connecpy.transport.client.connect_async import ConnectTransportAsync"
            in content
        )
        assert (
            "from connecpy.transport.client.grpc_async import GrpcTransportAsync"
            in content
        )

        # Verify the imports are properly configured
        assert "# noqa: PLC0415" in content  # Import suppression for late imports


def test_transport_api_not_generated_by_default():
    """Test that Transport API is NOT generated without transport_api=true."""

    proto_content = """
syntax = "proto3";
package test;

message Request {
    string data = 1;
}

message Response {
    string result = 1;
}

service TestService {
    rpc TestMethod(Request) returns (Response);
}
"""

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)

        # Write proto file
        proto_file = tmpdir_path / "test.proto"
        proto_file.write_text(proto_content)

        # Build the plugin first
        plugin_dir = Path(__file__).parent.parent.parent / "protoc-gen-connecpy"
        build_result = subprocess.run(
            ["go", "build", "-o", str(tmpdir_path / "protoc-gen-connecpy")],
            check=False,
            cwd=plugin_dir,
            capture_output=True,
            text=True,
        )

        if build_result.returncode != 0:
            pytest.skip(f"Failed to build plugin: {build_result.stderr}")

        # Generate code WITHOUT Transport API enabled
        result = subprocess.run(
            [
                "protoc",
                f"--plugin=protoc-gen-connecpy={tmpdir_path / 'protoc-gen-connecpy'}",
                f"--connecpy_out={tmpdir}",
                f"--python_out={tmpdir}",
                f"-I{tmpdir}",
                str(proto_file),
            ],
            check=False,
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            pytest.skip(f"protoc failed: {result.stderr}")

        # Check that generated file does NOT contain Transport API code
        generated_file = tmpdir_path / "test_connecpy.py"
        assert generated_file.exists(), "Generated file not found"

        content = generated_file.read_text()

        # Check that Transport API specific code is NOT present
        assert "class TestServiceClientProtocol(Protocol):" not in content
        assert "def create_client(" not in content
        assert "from connecpy.transport.client" not in content
