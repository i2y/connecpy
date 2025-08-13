import pytest
from example.haberdasher_connecpy import (
    Haberdasher,
    HaberdasherASGIApplication,
    HaberdasherClient,
    HaberdasherClientSync,
    HaberdasherSync,
    HaberdasherWSGIApplication,
)
from example.haberdasher_pb2 import Hat, Size
from httpx import (
    ASGITransport,
    AsyncClient,
    Client,
    WSGITransport,
)


@pytest.mark.parametrize("compression", ["gzip", "identity", None])
def test_roundtrip_sync(compression: str):
    class RoundtripHaberdasherSync(HaberdasherSync):
        def MakeHat(self, request, ctx):
            return Hat(size=request.inches, color="green")

    app = HaberdasherWSGIApplication(RoundtripHaberdasherSync())
    with HaberdasherClientSync(
        "http://localhost",
        session=Client(transport=WSGITransport(app=app)),
        send_compression=compression,
        accept_compression=[compression] if compression else None,
    ) as client:
        response = client.MakeHat(request=Size(inches=10))
    assert response.size == 10
    assert response.color == "green"


@pytest.mark.parametrize("compression", ["gzip", "identity"])
@pytest.mark.asyncio
async def test_roundtrip_async(compression: str):
    class DetailsHaberdasher(Haberdasher):
        async def MakeHat(self, request, ctx):
            return Hat(size=request.inches, color="green")

    app = HaberdasherASGIApplication(DetailsHaberdasher())
    transport = ASGITransport(app)  # pyright:ignore[reportArgumentType] - httpx type is not complete
    async with HaberdasherClient(
        "http://localhost",
        session=AsyncClient(transport=transport),
        send_compression=compression,
        accept_compression=[compression] if compression else None,
    ) as client:
        response = await client.MakeHat(request=Size(inches=10))
    assert response.size == 10
    assert response.color == "green"


@pytest.mark.parametrize("compression", ["br", "zstd"])
def test_invalid_compression_sync(compression: str):
    class RoundtripHaberdasherSync(HaberdasherSync):
        def MakeHat(self, request, ctx):
            return Hat(size=request.inches, color="green")

    app = HaberdasherWSGIApplication(RoundtripHaberdasherSync())

    with pytest.raises(ValueError) as exc_info:
        HaberdasherClientSync(
            "http://localhost",
            session=Client(transport=WSGITransport(app=app)),
            send_compression=compression,
            accept_compression=[compression] if compression else None,
        )
    assert (
        str(exc_info.value)
        == f"Unsupported compression method: {compression}. Available methods: gzip, identity"
    )


@pytest.mark.parametrize("compression", ["br", "zstd"])
@pytest.mark.asyncio
async def test_invalid_compression_async(compression: str):
    class DetailsHaberdasher(Haberdasher):
        async def MakeHat(self, request, ctx):
            return Hat(size=request.inches, color="green")

    app = HaberdasherASGIApplication(DetailsHaberdasher())
    transport = ASGITransport(app)  # pyright:ignore[reportArgumentType] - httpx type is not complete
    with pytest.raises(ValueError) as exc_info:
        HaberdasherClient(
            "http://localhost",
            session=AsyncClient(transport=transport),
            send_compression=compression,
            accept_compression=[compression] if compression else None,
        )
    assert (
        str(exc_info.value)
        == f"Unsupported compression method: {compression}. Available methods: gzip, identity"
    )
