import pytest
from unittest.mock import AsyncMock, Mock
from connecpy.compression import GenericEncodingMiddleware


@pytest.mark.asyncio
async def test_call_non_http_scope():
    app = AsyncMock()
    middleware_map = {}
    middleware = GenericEncodingMiddleware(app, middleware_map)
    scope = {"type": "websocket"}
    receive = Mock()
    send = Mock()

    await middleware(scope, receive, send)

    app.assert_awaited_once_with(scope, receive, send)


@pytest.mark.asyncio
async def test_call_no_accept_encoding():
    app = AsyncMock()
    middleware_map = {}
    middleware = GenericEncodingMiddleware(app, middleware_map)
    scope = {
        "type": "http",
        "headers": [],
    }
    receive = Mock()
    send = Mock()

    await middleware(scope, receive, send)

    app.assert_awaited_once_with(scope, receive, send)


@pytest.mark.asyncio
async def test_call_with_matching_encoding():
    mock_middleware = AsyncMock()
    middleware_map = {"gzip": mock_middleware}
    app = AsyncMock()
    middleware = GenericEncodingMiddleware(app, middleware_map)
    scope = {
        "type": "http",
        "headers": [(b"accept-encoding", b"gzip, deflate")],
    }
    receive = Mock()
    send = Mock()

    await middleware(scope, receive, send)

    mock_middleware.assert_awaited_once_with(scope, receive, send)
    app.assert_not_called()


@pytest.mark.asyncio
async def test_call_with_no_matching_encoding():
    app = AsyncMock()
    br = AsyncMock()
    middleware_map = {"br": br}
    middleware = GenericEncodingMiddleware(app, middleware_map)
    scope = {
        "type": "http",
        "headers": [(b"accept-encoding", b"gzip, deflate")],
    }
    receive = Mock()
    send = Mock()

    try:
        await middleware(scope, receive, send)
    except NotImplementedError as e:
        assert (
            "Unsupported Content-Encoding: ['gzip', 'deflate']. Supported encodings: ['br', 'identity']"
            in str(e)
        )

    app.assert_not_called()
    br.assert_not_called()
