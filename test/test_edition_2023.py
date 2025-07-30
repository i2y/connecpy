"""
Basic test to verify Proto Editions 2023 files don't crash protoc-gen-connecpy.
"""

from example.haberdasher_edition_2023_connecpy import (
    Haberdasher,
    HaberdasherASGIApplication,
    HaberdasherClient,
    HaberdasherSync,
    HaberdasherWSGIApplication,
    HaberdasherClientSync,
)
from example.haberdasher_edition_2023_pb2 import Hat, Size

from connecpy.server import ServiceContext


def test_edition_2023_service_generation():
    """Test that protoc-gen-connecpy doesn't crash on Edition 2023 files and generates working code."""

    # Create a simple service implementation
    class TestHaberdasher(Haberdasher):
        async def MakeHat(self, req: Size, ctx: ServiceContext) -> Hat:
            return Hat(size=req.inches, color="blue", name="test")

    # Verify the service can be instantiated
    service = TestHaberdasher()
    app = HaberdasherASGIApplication(service)
    assert app is not None

    # Verify sync version works too
    class TestHaberdasherSync(HaberdasherSync):
        def MakeHat(self, req: Size, ctx: ServiceContext) -> Hat:
            return Hat(size=req.inches, color="red", name="test")

    sync_service = TestHaberdasherSync()
    sync_app = HaberdasherWSGIApplication(sync_service)
    assert sync_app is not None


def test_edition_2023_client_generation():
    """Test that Edition 2023 proto generates working client code."""
    # Verify clients can be instantiated
    client = HaberdasherClient("http://localhost:3000")
    assert client is not None

    sync_client = HaberdasherClientSync("http://localhost:3000")
    assert sync_client is not None
