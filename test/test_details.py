import pytest
from google.protobuf.any import pack
from google.protobuf.struct_pb2 import Struct, Value
from httpx import (
    ASGITransport,
    AsyncClient,
    Client,
    WSGITransport,
)

from connecpy.code import Code
from connecpy.exceptions import ConnecpyException
from example.haberdasher_connecpy import (
    Haberdasher,
    HaberdasherASGIApplication,
    HaberdasherClient,
    HaberdasherClientSync,
    HaberdasherSync,
    HaberdasherWSGIApplication,
)
from example.haberdasher_pb2 import Size


def test_details_sync():
    class DetailsHaberdasherSync(HaberdasherSync):
        def make_hat(self, request, ctx):
            raise ConnecpyException(
                Code.RESOURCE_EXHAUSTED,
                "Resource exhausted",
                details=[
                    Struct(fields={"animal": Value(string_value="bear")}),
                    pack(Struct(fields={"color": Value(string_value="red")})),
                ],
            )

    app = HaberdasherWSGIApplication(DetailsHaberdasherSync())
    with (
        HaberdasherClientSync(
            "http://localhost", session=Client(transport=WSGITransport(app=app))
        ) as client,
        pytest.raises(ConnecpyException) as exc_info,
    ):
        client.make_hat(request=Size(inches=10))
    assert exc_info.value.code == Code.RESOURCE_EXHAUSTED
    assert exc_info.value.message == "Resource exhausted"
    assert len(exc_info.value.details) == 2
    s0 = Struct()
    assert exc_info.value.details[0].Unpack(s0)
    assert s0.fields["animal"].string_value == "bear"
    s1 = Struct()
    assert exc_info.value.details[1].Unpack(s1)
    assert s1.fields["color"].string_value == "red"


@pytest.mark.asyncio
async def test_details_async():
    class DetailsHaberdasher(Haberdasher):
        async def make_hat(self, request, ctx):
            raise ConnecpyException(
                Code.RESOURCE_EXHAUSTED,
                "Resource exhausted",
                details=[
                    Struct(fields={"animal": Value(string_value="bear")}),
                    pack(Struct(fields={"color": Value(string_value="red")})),
                ],
            )

    app = HaberdasherASGIApplication(DetailsHaberdasher())
    transport = ASGITransport(app)  # pyright:ignore[reportArgumentType] - httpx type is not complete
    async with HaberdasherClient(
        "http://localhost", session=AsyncClient(transport=transport)
    ) as client:
        with pytest.raises(ConnecpyException) as exc_info:
            await client.make_hat(request=Size(inches=10))
    assert exc_info.value.code == Code.RESOURCE_EXHAUSTED
    assert exc_info.value.message == "Resource exhausted"
    assert len(exc_info.value.details) == 2
    s0 = Struct()
    assert exc_info.value.details[0].Unpack(s0)
    assert s0.fields["animal"].string_value == "bear"
    s1 = Struct()
    assert exc_info.value.details[1].Unpack(s1)
    assert s1.fields["color"].string_value == "red"
