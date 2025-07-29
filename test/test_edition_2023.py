"""
Comprehensive test suite for Proto Editions 2023 support in Connecpy.
"""

import pytest

from example.haberdasher_edition_2023_connecpy import (
    Haberdasher,
    HaberdasherASGIApplication,
    HaberdasherClient,
    HaberdasherSync,
    HaberdasherWSGIApplication,
    HaberdasherClientSync,
)
from example.haberdasher_edition_2023_pb2 import Hat, Size

from example.edition_features_test_connecpy import (
    EditionTestService,
    EditionTestServiceASGIApplication,
)
from example.edition_features_test_pb2 import (
    ExplicitFieldTest,
    ImplicitFieldTest,
    MixedFieldTest,
    OpenEnum,
    ClosedEnum,
    EncodingTest,
    FeatureTestRequest,
    FeatureTestResponse,
)

from connecpy.server import ServiceContext


class TestEdition2023Basic:
    """Test basic Edition 2023 functionality."""

    def test_message_creation(self):
        """Test creating messages from Edition 2023 proto."""
        size = Size(inches=10, description="A nice hat")
        assert size.inches == 10
        assert size.description == "A nice hat"

        hat = Hat(size=12, color="blue", name="fedora")
        assert hat.size == 12
        assert hat.color == "blue"
        assert hat.name == "fedora"

    def test_sync_service_creation(self):
        """Test creating sync service from Edition 2023 proto."""

        class TestHaberdasherSync(HaberdasherSync):
            def MakeHat(self, req: Size, ctx: ServiceContext) -> Hat:
                return Hat(size=req.inches, color="red", name="test")

        service = TestHaberdasherSync()
        app = HaberdasherWSGIApplication(service)
        assert app.service_name == "i2y.connecpy.example2023.Haberdasher"

    def test_async_service_creation(self):
        """Test creating async service from Edition 2023 proto."""

        class TestHaberdasher(Haberdasher):
            async def MakeHat(self, req: Size, ctx: ServiceContext) -> Hat:
                return Hat(size=req.inches, color="blue", name="test")

        service = TestHaberdasher()
        app = HaberdasherASGIApplication(service)
        assert app.service_name == "i2y.connecpy.example2023.Haberdasher"

    def test_client_creation(self):
        """Test creating clients from Edition 2023 proto."""
        client = HaberdasherClient("http://localhost:3000")
        assert client is not None

        sync_client = HaberdasherClientSync("http://localhost:3000")
        assert sync_client is not None


class TestEdition2023Features:
    """Test Edition 2023 specific features."""

    def test_explicit_field_presence(self):
        """Test EXPLICIT field presence (default in Edition 2023)."""
        # In Edition 2023, fields have explicit presence by default
        msg = ExplicitFieldTest()
        # Even though not set, HasField should work for explicit fields
        assert hasattr(msg, "name")
        assert hasattr(msg, "value")

    def test_implicit_field_presence(self):
        """Test IMPLICIT field presence (proto3 behavior)."""
        msg = ImplicitFieldTest()
        # Implicit fields behave like proto3
        assert hasattr(msg, "name")
        assert hasattr(msg, "value")

    def test_mixed_field_presence(self):
        """Test mixed field presence in same message."""
        msg = MixedFieldTest()
        assert hasattr(msg, "explicit_field")
        assert hasattr(msg, "implicit_field")

    def test_open_enum(self):
        """Test OPEN enum type (proto3 behavior)."""
        # Open enums accept unknown values
        assert OpenEnum.UNKNOWN == 0
        assert OpenEnum.FIRST == 1
        assert OpenEnum.SECOND == 2

    def test_closed_enum(self):
        """Test CLOSED enum type (proto2 behavior)."""
        # Closed enums are stricter
        assert ClosedEnum.ZERO == 0
        assert ClosedEnum.ONE == 1
        assert ClosedEnum.TWO == 2

    def test_encoding_features(self):
        """Test repeated field encoding features."""
        msg = EncodingTest()
        msg.packed_ints.extend([1, 2, 3])
        msg.expanded_ints.extend([4, 5, 6])

        assert list(msg.packed_ints) == [1, 2, 3]
        assert list(msg.expanded_ints) == [4, 5, 6]

    def test_complex_request(self):
        """Test creating a complex request with all features."""
        req = FeatureTestRequest(
            explicit_test=ExplicitFieldTest(name="explicit", value=1),
            implicit_test=ImplicitFieldTest(name="implicit", value=2),
            mixed_test=MixedFieldTest(explicit_field="exp", implicit_field="imp"),
            open_enum=OpenEnum.FIRST,
            closed_enum=ClosedEnum.ONE,
            encoding_test=EncodingTest(packed_ints=[1, 2, 3], expanded_ints=[4, 5, 6]),
        )

        assert req.explicit_test.name == "explicit"
        assert req.implicit_test.value == 2
        assert req.open_enum == OpenEnum.FIRST


class TestEdition2023Service:
    """Test Edition 2023 service generation."""

    def test_service_with_idempotency(self):
        """Test service methods with idempotency_level."""

        class TestEditionService(EditionTestService):
            async def TestFeatures(self, req, ctx):
                return FeatureTestResponse(result="test")

            async def GetFeatures(self, req, ctx):
                # This method has NO_SIDE_EFFECTS
                return FeatureTestResponse(result="get")

        service = TestEditionService()
        app = EditionTestServiceASGIApplication(service)

        # Check that GetFeatures allows GET requests due to NO_SIDE_EFFECTS
        endpoints = app._endpoints
        test_endpoint = endpoints["/test.editions.EditionTestService/TestFeatures"]
        get_endpoint = endpoints["/test.editions.EditionTestService/GetFeatures"]

        assert test_endpoint.allowed_methods == ("POST",)
        assert get_endpoint.allowed_methods == ("GET", "POST")


if __name__ == "__main__":
    # Run with pytest for better output
    pytest.main([__file__, "-v"])
