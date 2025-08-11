import itertools

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient, Client, WSGITransport

from connecpy.request import RequestContext
from example.haberdasher_connecpy import (
    Haberdasher,
    HaberdasherASGIApplication,
    HaberdasherClient,
    HaberdasherClientSync,
    HaberdasherSync,
    HaberdasherWSGIApplication,
)
from example.haberdasher_pb2 import Hat, Size


class RequestInterceptor:
    def __init__(self):
        self.result = []

    async def on_start(self, ctx: RequestContext):
        return self.on_start_sync(ctx)

    async def on_end(self, token: str, ctx: RequestContext):
        self.on_end_sync(token, ctx)

    def on_start_sync(self, ctx: RequestContext):
        return f"Hello {ctx.method().name}"

    def on_end_sync(self, token: str, ctx: RequestContext):
        self.result.append(f"{token} and goodbye")


@pytest.fixture
def interceptor():
    return RequestInterceptor()


@pytest_asyncio.fixture
async def client_async(interceptor: RequestInterceptor):
    class SimpleHaberdasher(Haberdasher):
        async def MakeHat(self, req, ctx):
            return Hat(size=req.inches, color="green")

        async def MakeFlexibleHat(self, req, ctx):
            size = 0
            async for s in req:
                size += s.inches
            return Hat(size=size, color="red")

        async def MakeSimilarHats(self, req, ctx):
            yield Hat(size=req.inches, color="orange")
            yield Hat(size=req.inches, color="blue")

        async def MakeVariousHats(self, req, ctx):
            colors = itertools.cycle(("black", "white", "gold"))
            async for s in req:
                yield Hat(size=s.inches, color=next(colors))

    app = HaberdasherASGIApplication(SimpleHaberdasher(), interceptors=(interceptor,))
    transport = ASGITransport(app)  # pyright:ignore[reportArgumentType] - httpx type is not complete
    async with HaberdasherClient(
        "http://localhost",
        interceptors=(interceptor,),
        session=AsyncClient(transport=transport),
    ) as client:
        yield client


@pytest.mark.asyncio
async def test_intercept_unary_async(
    client_async: HaberdasherClient, interceptor: RequestInterceptor
):
    result = await client_async.MakeHat(Size(inches=10))
    assert result == Hat(size=10, color="green")
    assert interceptor.result == ["Hello MakeHat and goodbye"] * 2


@pytest.mark.asyncio
async def test_intercept_client_stream_async(
    client_async: HaberdasherClient, interceptor: RequestInterceptor
):
    async def requests():
        yield Size(inches=10)
        yield Size(inches=20)

    result = await client_async.MakeFlexibleHat(requests())
    assert result == Hat(size=30, color="red")
    assert interceptor.result == ["Hello MakeFlexibleHat and goodbye"] * 2


@pytest.mark.asyncio
async def test_intercept_server_stream_async(
    client_async: HaberdasherClient, interceptor: RequestInterceptor
):
    result = [r async for r in client_async.MakeSimilarHats(Size(inches=15))]

    assert result == [Hat(size=15, color="orange"), Hat(size=15, color="blue")]
    assert interceptor.result == ["Hello MakeSimilarHats and goodbye"] * 2


@pytest.mark.asyncio
async def test_intercept_bidi_stream_async(
    client_async: HaberdasherClient, interceptor: RequestInterceptor
):
    async def requests():
        yield Size(inches=25)
        yield Size(inches=35)
        yield Size(inches=45)

    result = [r async for r in client_async.MakeVariousHats(requests())]

    assert result == [
        Hat(size=25, color="black"),
        Hat(size=35, color="white"),
        Hat(size=45, color="gold"),
    ]
    assert interceptor.result == ["Hello MakeVariousHats and goodbye"] * 2


@pytest.fixture
def client_sync(interceptor: RequestInterceptor):
    class SimpleHaberdasherSync(HaberdasherSync):
        def MakeHat(self, req, ctx):
            return Hat(size=req.inches, color="green")

        def MakeFlexibleHat(self, req, ctx):
            size = 0
            for s in req:
                size += s.inches
            return Hat(size=size, color="red")

        def MakeSimilarHats(self, req, ctx):
            yield Hat(size=req.inches, color="orange")
            yield Hat(size=req.inches, color="blue")

        def MakeVariousHats(self, req, ctx):
            colors = itertools.cycle(("black", "white", "gold"))
            requests = [*req]
            for s in requests:
                yield Hat(size=s.inches, color=next(colors))

    app = HaberdasherWSGIApplication(
        SimpleHaberdasherSync(), interceptors=(interceptor,)
    )
    transport = WSGITransport(app)  # pyright:ignore[reportArgumentType] - httpx type is not complete
    with HaberdasherClientSync(
        "http://localhost",
        interceptors=(interceptor,),
        session=Client(transport=transport),
    ) as client:
        yield client


def test_intercept_unary_sync(
    client_sync: HaberdasherClientSync, interceptor: RequestInterceptor
):
    result = client_sync.MakeHat(Size(inches=10))
    assert result == Hat(size=10, color="green")
    assert interceptor.result == ["Hello MakeHat and goodbye"] * 2


def test_intercept_client_stream_sync(
    client_sync: HaberdasherClientSync, interceptor: RequestInterceptor
):
    def requests():
        yield Size(inches=10)
        yield Size(inches=20)

    result = client_sync.MakeFlexibleHat(requests())
    assert result == Hat(size=30, color="red")
    assert interceptor.result == ["Hello MakeFlexibleHat and goodbye"] * 2


def test_intercept_server_stream_sync(
    client_sync: HaberdasherClientSync, interceptor: RequestInterceptor
):
    result = [r for r in client_sync.MakeSimilarHats(Size(inches=15))]

    assert result == [Hat(size=15, color="orange"), Hat(size=15, color="blue")]
    assert interceptor.result == ["Hello MakeSimilarHats and goodbye"] * 2


def test_intercept_bidi_stream_sync(
    client_sync: HaberdasherClientSync, interceptor: RequestInterceptor
):
    def requests():
        yield Size(inches=25)
        yield Size(inches=35)
        yield Size(inches=45)

    result = [r for r in client_sync.MakeVariousHats(requests())]

    assert result == [
        Hat(size=25, color="black"),
        Hat(size=35, color="white"),
        Hat(size=45, color="gold"),
    ]
    assert interceptor.result == ["Hello MakeVariousHats and goodbye"] * 2
