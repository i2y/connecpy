from httpx import (
    ASGITransport,
    AsyncClient,
    Client,
    WSGITransport,
)
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


_roundtrip_cases = [
    (False),
    (True),
]


@pytest.mark.parametrize("proto_json", _roundtrip_cases)
def test_roundtrip_sync(proto_json: bool):
    class RoundtripHaberdasherSync(HaberdasherSync):
        def MakeHat(self, req, ctx):
            return Hat(size=req.inches, color="green")

    app = HaberdasherWSGIApplication(RoundtripHaberdasherSync())
    with HaberdasherClientSync(
        "http://localhost",
        session=Client(transport=WSGITransport(app=app)),
        proto_json=proto_json,
    ) as client:
        response = client.MakeHat(request=Size(inches=10))
    assert response.size == 10
    assert response.color == "green"


@pytest.mark.parametrize("proto_json", _roundtrip_cases)
@pytest.mark.asyncio
async def test_details_async(proto_json: bool):
    class DetailsHaberdasher(Haberdasher):
        async def MakeHat(self, req, ctx):
            return Hat(size=req.inches, color="green")

    app = HaberdasherASGIApplication(DetailsHaberdasher())
    transport = ASGITransport(app)  # pyright:ignore[reportArgumentType] - httpx type is not complete
    async with HaberdasherClient(
        "http://localhost",
        session=AsyncClient(transport=transport),
        proto_json=proto_json,
    ) as client:
        response = await client.MakeHat(request=Size(inches=10))
    assert response.size == 10
    assert response.color == "green"
