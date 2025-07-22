from httpx import (
    ASGITransport,
    AsyncClient,
    Client,
    WSGITransport,
)
import pytest
from connecpy.client import ResponseMetadata
from connecpy.errors import Errors
from connecpy.exceptions import ConnecpyServerException
from example.haberdasher_connecpy import (
    Haberdasher,
    HaberdasherASGIApplication,
    HaberdasherClient,
    HaberdasherClientSync,
    HaberdasherSync,
    HaberdasherWSGIApplication,
)
from example.haberdasher_pb2 import Hat, Size
from google.protobuf.any import pack
from google.protobuf.struct_pb2 import Struct, Value


def test_details_sync():
    class DetailsHaberdasherSync(HaberdasherSync):
        def MakeHat(self, req, ctx):
            raise ConnecpyServerException(
                code=Errors.ResourceExhausted,
                message="Resource exhausted",
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
        pytest.raises(ConnecpyServerException) as exc_info,
    ):
        client.MakeHat(request=Size(inches=10))
    assert exc_info.value.code == Errors.ResourceExhausted
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
        async def MakeHat(self, req, ctx):
            raise ConnecpyServerException(
                code=Errors.ResourceExhausted,
                message="Resource exhausted",
                details=[
                    Struct(fields={"animal": Value(string_value="bear")}),
                    pack(Struct(fields={"color": Value(string_value="red")})),
                ],
            )

    app = HaberdasherASGIApplication(DetailsHaberdasher())
    async with HaberdasherClient(
        "http://localhost", session=AsyncClient(transport=ASGITransport(app=app))
    ) as client:
        with pytest.raises(ConnecpyServerException) as exc_info:
            await client.MakeHat(request=Size(inches=10))
    assert exc_info.value.code == Errors.ResourceExhausted
    assert exc_info.value.message == "Resource exhausted"
    assert len(exc_info.value.details) == 2
    s0 = Struct()
    assert exc_info.value.details[0].Unpack(s0)
    assert s0.fields["animal"].string_value == "bear"
    s1 = Struct()
    assert exc_info.value.details[1].Unpack(s1)
    assert s1.fields["color"].string_value == "red"
