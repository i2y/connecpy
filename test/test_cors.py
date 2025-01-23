import pytest
from starlette.responses import Response
from connecpy.cors import middleware, CORSConfig, CORSMiddleware
from starlette.testclient import TestClient
import asyncio


@pytest.fixture
def config():
    return CORSConfig()


@pytest.fixture
def app(config):
    async def app_scope(scope, receive, send):
        if scope["type"] != "http":
            return
        response = Response("OK")
        await response(scope, receive, send)

    return middleware(app_scope, config)


def test_preflight_request(app):
    client = TestClient(app)
    response = client.options(
        "/",
        headers={
            "Origin": "http://example.com",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.status_code == 204
    assert response.headers["access-control-allow-origin"] == "*"
    assert "POST, GET" in response.headers["access-control-allow-methods"]
    assert "Content-Type" in response.headers["access-control-allow-headers"]
    assert (
        "Connect-Protocol-Version" in response.headers["access-control-allow-headers"]
    )
    assert "Connect-Timeout-Ms" in response.headers["access-control-allow-headers"]
    assert "X-User-Agent" in response.headers["access-control-allow-headers"]
    assert response.headers["access-control-max-age"] == "86400"


def test_preflight_request_custom_config():
    config = CORSConfig(
        allow_origin="http://example.com",
        allow_methods=("POST", "GET", "PUT"),
        allow_headers=("Content-Type", "X-User-Agent"),
        access_control_max_age=3600,
    )

    async def app_scope(scope, receive, send):
        if scope["type"] != "http":
            return
        response = Response("OK")
        await response(scope, receive, send)

    app = middleware(app_scope, config)

    client = TestClient(app)
    response = client.options(
        "/",
        headers={
            "Origin": "http://example.com",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == 204
    assert response.headers["access-control-allow-origin"] == "http://example.com"
    assert "POST, GET, PUT" in response.headers["access-control-allow-methods"]
    assert "Content-Type" in response.headers["access-control-allow-headers"]
    assert "X-User-Agent" in response.headers["access-control-allow-headers"]
    assert (
        "Connect-Protocol-Version"
        not in response.headers["access-control-allow-headers"]
    )
    assert "Connect-Timeout-Ms" not in response.headers["access-control-allow-headers"]
    assert response.headers["access-control-max-age"] == "3600"


def test_simple_request(app):
    client = TestClient(app)
    response = client.get("/", headers={"Origin": "http://example.com"})
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "*"
    assert response.text == "OK"


def test_simple_request_custom_config():
    config = CORSConfig(allow_origin="http://example.com")

    async def app_scope(scope, receive, send):
        if scope["type"] != "http":
            return
        response = Response("OK")
        await response(scope, receive, send)

    app = middleware(app_scope, config)

    client = TestClient(app)
    response = client.get("/", headers={"Origin": "http://example.com"})
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://example.com"
    assert response.text == "OK"


def test_non_http_scope(app):
    async def non_http_scope():
        scope = {"type": "websocket"}
        receive = lambda: None
        send = lambda message: None
        await app(scope, receive, send)

    asyncio.run(non_http_scope())


def test_cors_middleware_class():
    async def app_scope(scope, receive, send):
        if scope["type"] != "http":
            return
        response = Response("OK")
        await response(scope, receive, send)

    client = TestClient(CORSMiddleware(app_scope))
    response = client.options(
        "/",
        headers={
            "Origin": "http://example.com",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.status_code == 204
    assert response.headers["access-control-allow-origin"] == "*"
    assert "POST, GET" in response.headers["access-control-allow-methods"]
    assert "Content-Type" in response.headers["access-control-allow-headers"]
    assert (
        "Connect-Protocol-Version" in response.headers["access-control-allow-headers"]
    )
    assert "Connect-Timeout-Ms" in response.headers["access-control-allow-headers"]
    assert "X-User-Agent" in response.headers["access-control-allow-headers"]
    assert response.headers["access-control-max-age"] == "86400"


def test_cors_middleware_class_custom_config():
    config = CORSConfig(
        allow_origin="http://example.com",
        allow_methods=("POST", "GET", "PUT"),
        allow_headers=("Content-Type", "X-User-Agent"),
        access_control_max_age=3600,
    )

    async def app_scope(scope, receive, send):
        if scope["type"] != "http":
            return
        response = Response("OK")
        await response(scope, receive, send)

    client = TestClient(CORSMiddleware(app_scope, config=config))
    response = client.options(
        "/",
        headers={
            "Origin": "http://example.com",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == 204
    assert response.headers["access-control-allow-origin"] == "http://example.com"
    assert "POST, GET, PUT" in response.headers["access-control-allow-methods"]
    assert "Content-Type" in response.headers["access-control-allow-headers"]
    assert "X-User-Agent" in response.headers["access-control-allow-headers"]
    assert (
        "Connect-Protocol-Version"
        not in response.headers["access-control-allow-headers"]
    )
    assert "Connect-Timeout-Ms" not in response.headers["access-control-allow-headers"]
    assert response.headers["access-control-max-age"] == "3600"
