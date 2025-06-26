import threading

import httpx
import pytest
from wsgiref.simple_server import make_server, WSGIServer
from connecpy.context import ClientContext
from connecpy.wsgi import ConnecpyWSGIApp
from example.wsgi_service import HaberdasherService
from example.haberdasher_pb2 import Size
from example.haberdasher_connecpy import (
    AsyncHaberdasherClient,
    HaberdasherClient,
    HaberdasherServerSync,
)


@pytest.fixture(scope="module")
def sync_server():
    service = HaberdasherService()
    server = HaberdasherServerSync(service=service)
    app = ConnecpyWSGIApp()
    app.add_service(server)

    with make_server("", 0, app) as httpd:
        thread = threading.Thread(target=httpd.serve_forever)
        thread.daemon = True
        thread.start()
        try:
            yield httpd
        finally:
            httpd.shutdown()


def test_sync_client_basic(sync_server: WSGIServer):
    with HaberdasherClient(f"http://localhost:{sync_server.server_port}") as client:
        response = client.MakeHat(request=Size(inches=10))
        assert response.size == 10
    assert client._session.is_closed


def test_sync_client_custom_session_and_header(sync_server: WSGIServer):
    recorded_request = None

    def record_request(request):
        nonlocal recorded_request
        recorded_request = request

    session = httpx.Client(event_hooks={"request": [record_request]})
    with HaberdasherClient(
        f"http://localhost:{sync_server.server_port}", session=session
    ) as client:
        response = client.MakeHat(
            request=Size(inches=10), ctx=ClientContext(headers={"x-animal": "bear"})
        )
        assert response.size == 10
    assert not session.is_closed
    assert recorded_request is not None
    assert recorded_request.headers.get("x-animal") == "bear"


@pytest.mark.asyncio
async def test_async_client_basic(sync_server: WSGIServer):
    async with AsyncHaberdasherClient(
        f"http://localhost:{sync_server.server_port}"
    ) as client:
        response = await client.MakeHat(request=Size(inches=10))
        assert response.size == 10
    assert client._session.is_closed


@pytest.mark.asyncio
async def test_async_client_custom_session_and_header(sync_server: WSGIServer):
    recorded_request = None

    async def record_request(request):
        nonlocal recorded_request
        recorded_request = request

    session = httpx.AsyncClient(event_hooks={"request": [record_request]})
    async with AsyncHaberdasherClient(
        f"http://localhost:{sync_server.server_port}", session=session
    ) as client:
        response = await client.MakeHat(
            request=Size(inches=10), ctx=ClientContext(headers={"x-animal": "bear"})
        )
        assert response.size == 10
    assert not session.is_closed
    assert recorded_request is not None
    assert recorded_request.headers.get("x-animal") == "bear"
