from typing import AsyncIterator, Iterator

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
            async for h in client.MakeSimilarHats(request=Size(inches=10)):
                hats.append(h)
    assert hats[0].size == 10
    assert hats[0].color == "green"
    assert hats[1].size == 10
    assert hats[1].color == "red"
    assert hats[2].size == 10
    assert hats[2].color == "blue"

    assert exc_info.value.code == Code.RESOURCE_EXHAUSTED
    assert exc_info.value.message == "No more hats available"


@pytest.mark.parametrize("client_bad", [False, True])
@pytest.mark.parametrize("compression", ["gzip", "br", "zstd", "identity"])
def test_message_limit_sync(
    client_bad: bool,
    compression: str,
):
    requests: list[Size] = []
    responses: list[Hat] = []

    good_size = Size(description="good")
    bad_size = Size(description="X" * 1000)
    good_hat = Hat(color="good")
    bad_hat = Hat(color="X" * 1000)

    class LargeHaberdasher(HaberdasherSync):
        def MakeHat(self, req, ctx):
            requests.append(req)
            return good_hat if client_bad else bad_hat

        def MakeVariousHats(self, req: Iterator[Size], ctx) -> Iterator[Hat]:
            for size in req:
                requests.append(size)
            yield Hat(color="good")
            yield good_hat if client_bad else bad_hat

    app = HaberdasherWSGIApplication(LargeHaberdasher(), read_max_bytes=100)
    transport = WSGITransport(app)  # pyright:ignore[reportArgumentType] - httpx type is not complete
    with HaberdasherClientSync(
        "http://localhost",
        session=Client(transport=transport),
        send_compression=compression,
        accept_compression=[compression] if compression else None,
        read_max_bytes=100,
    ) as client:
        with pytest.raises(ConnecpyException) as exc_info:
            client.MakeHat(request=bad_size if client_bad else good_size)
        assert exc_info.value.code == Code.RESOURCE_EXHAUSTED
        assert exc_info.value.message == "message is larger than configured max 100"
        if client_bad:
            assert len(requests) == 0
        else:
            assert len(requests) == 1
        assert len(responses) == 0

        requests = []
        responses = []

        with pytest.raises(ConnecpyException) as exc_info:

            def request_stream():
                yield good_size
                yield bad_size if client_bad else good_size

            for h in client.MakeVariousHats(request=request_stream()):
                responses.append(h)
        assert exc_info.value.code == Code.RESOURCE_EXHAUSTED
        assert exc_info.value.message == "message is larger than configured max 100"
        if client_bad:
            assert len(requests) == 1
            assert len(responses) == 0
        else:
            assert len(requests) == 2
            assert len(responses) == 1


@pytest.mark.parametrize("client_bad", [False, True])
@pytest.mark.parametrize("compression", ["gzip", "br", "zstd", "identity"])
@pytest.mark.asyncio
async def test_message_limit_async(
    client_bad: bool,
    compression: str,
):
    requests: list[Size] = []
    responses: list[Hat] = []

    good_size = Size(description="good")
    bad_size = Size(description="X" * 1000)
    good_hat = Hat(color="good")
    bad_hat = Hat(color="X" * 1000)

    class LargeHaberdasher(Haberdasher):
        async def MakeHat(self, req, ctx):
            requests.append(req)
            return good_hat if client_bad else bad_hat

        async def MakeVariousHats(
            self, req: AsyncIterator[Size], ctx
        ) -> AsyncIterator[Hat]:
            async for size in req:
                requests.append(size)
            yield Hat(color="good")
            yield good_hat if client_bad else bad_hat

    app = HaberdasherASGIApplication(LargeHaberdasher(), read_max_bytes=100)
    transport = ASGITransport(app)  # pyright:ignore[reportArgumentType] - httpx type is not complete
    async with HaberdasherClient(
        "http://localhost",
        session=AsyncClient(transport=transport),
        send_compression=compression,
        accept_compression=[compression] if compression else None,
        read_max_bytes=100,
    ) as client:
        with pytest.raises(ConnecpyException) as exc_info:
            await client.MakeHat(request=bad_size if client_bad else good_size)
        assert exc_info.value.code == Code.RESOURCE_EXHAUSTED
        assert exc_info.value.message == "message is larger than configured max 100"
        if client_bad:
            assert len(requests) == 0
        else:
            assert len(requests) == 1
        assert len(responses) == 0

        requests = []
        responses = []

        with pytest.raises(ConnecpyException) as exc_info:

            async def request_stream():
                yield good_size
                yield bad_size if client_bad else good_size

            async for h in client.MakeVariousHats(request=request_stream()):
                responses.append(h)
        assert exc_info.value.code == Code.RESOURCE_EXHAUSTED
        assert exc_info.value.message == "message is larger than configured max 100"
        if client_bad:
            assert len(requests) == 1
            assert len(responses) == 0
        else:
            assert len(requests) == 2
            assert len(responses) == 1
