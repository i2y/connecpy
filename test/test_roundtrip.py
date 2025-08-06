import pytest
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
from example.haberdasher_pb2 import Hat, Size


@pytest.mark.parametrize("proto_json", [False, True])
@pytest.mark.parametrize("compression", ["gzip", "br", "zstd", "identity", None])
def test_roundtrip_sync(proto_json: bool, compression: str):
    class RoundtripHaberdasherSync(HaberdasherSync):
        def MakeHat(self, req, ctx):
            return Hat(size=req.inches, color="green")

    app = HaberdasherWSGIApplication(RoundtripHaberdasherSync())
    with HaberdasherClientSync(
        "http://localhost",
        session=Client(transport=WSGITransport(app=app)),
        proto_json=proto_json,
        send_compression=compression,
        accept_compression=[compression] if compression else None,
    ) as client:
        response = client.MakeHat(request=Size(inches=10))
    assert response.size == 10
    assert response.color == "green"


@pytest.mark.parametrize("proto_json", [False, True])
@pytest.mark.parametrize("compression", ["gzip", "br", "zstd", "identity"])
@pytest.mark.asyncio
async def test_roundtrip_async(proto_json: bool, compression: str):
    class DetailsHaberdasher(Haberdasher):
        async def MakeHat(self, req, ctx):
            return Hat(size=req.inches, color="green")

    app = HaberdasherASGIApplication(DetailsHaberdasher())
    transport = ASGITransport(app)  # pyright:ignore[reportArgumentType] - httpx type is not complete
    async with HaberdasherClient(
        "http://localhost",
        session=AsyncClient(transport=transport),
        proto_json=proto_json,
        send_compression=compression,
        accept_compression=[compression] if compression else None,
    ) as client:
        response = await client.MakeHat(request=Size(inches=10))
    assert response.size == 10
    assert response.color == "green"


@pytest.mark.parametrize("proto_json", [False, True])
@pytest.mark.parametrize("compression", ["gzip", "br", "zstd", "identity"])
@pytest.mark.asyncio
async def test_roundtrip_response_stream_async(proto_json: bool, compression: str):
    class StreamingHaberdasher(Haberdasher):
        async def MakeSimilarHats(self, req, ctx):
            yield Hat(size=req.inches, color="green")
            yield Hat(size=req.inches, color="red")
            yield Hat(size=req.inches, color="blue")
            raise ConnecpyException(Code.RESOURCE_EXHAUSTED, "No more hats available")

    app = HaberdasherASGIApplication(StreamingHaberdasher())
    transport = ASGITransport(app)  # pyright:ignore[reportArgumentType] - httpx type is not complete

    hats: list[Hat] = []
    async with HaberdasherClient(
        "http://localhost",
        session=AsyncClient(transport=transport),
        proto_json=proto_json,
        send_compression=compression,
        accept_compression=[compression] if compression else None,
    ) as client:
        with pytest.raises(ConnecpyException) as exc_info:
            async for h in await client.MakeSimilarHats(request=Size(inches=10)):
                hats.append(h)
    assert hats[0].size == 10
    assert hats[0].color == "green"
    assert hats[1].size == 10
    assert hats[1].color == "red"
    assert hats[2].size == 10
    assert hats[2].color == "blue"

    assert exc_info.value.code == Code.RESOURCE_EXHAUSTED
    assert exc_info.value.message == "No more hats available"
