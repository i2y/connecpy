"""
Basic test to verify Proto Editions 2023 files don't crash protoc-gen-connecpy.
"""

from connecpy.request import RequestContext
from example.haberdasher_edition_2023_connecpy import (
    Haberdasher,
    HaberdasherASGIApplication,
    HaberdasherClient,
    HaberdasherClientSync,
    HaberdasherSync,
    HaberdasherWSGIApplication,
)
from example.haberdasher_edition_2023_pb2 import Hat, Size


def test_edition_2023_service_generation():
    """Test that Edition 2023 generated code can be imported and instantiated correctly."""

    # Create a simple service implementation
    class TestHaberdasher(Haberdasher):
        async def MakeHat(self, request: Size, ctx: RequestContext) -> Hat:
            return Hat(size=request.inches, color="blue", name="test")

    # Verify the service can be instantiated
    service = TestHaberdasher()
    app = HaberdasherASGIApplication(service)
    assert app is not None

    # Verify sync version works too
    class TestHaberdasherSync(HaberdasherSync):
        def MakeHat(self, request: Size, ctx: RequestContext) -> Hat:
            return Hat(size=request.inches, color="red", name="test")

    sync_service = TestHaberdasherSync()
    sync_app = HaberdasherWSGIApplication(sync_service)
    assert sync_app is not None


def test_edition_2023_client_generation():
    """Test that Edition 2023 generated client code can be instantiated correctly."""
    # Verify clients can be instantiated
    client = HaberdasherClient("http://localhost:3000")
    assert client is not None

    sync_client = HaberdasherClientSync("http://localhost:3000")
    assert sync_client is not None
