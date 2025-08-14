import threading
import time
from http import HTTPStatus
from typing import Optional
from wsgiref.simple_server import WSGIServer, make_server

import pytest
from httpx import (
    ASGITransport,
    AsyncClient,
    Client,
    MockTransport,
    Request,
    Response,
    Timeout,
    WSGITransport,
)
from pytest import param as p

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

_errors = [
    (Code.CANCELED, "Operation was cancelled", 499),
    (Code.UNKNOWN, "An unknown error occurred", 500),
    (Code.INVALID_ARGUMENT, "That's not right", 400),
    (Code.DEADLINE_EXCEEDED, "Deadline exceeded", 504),
    (Code.NOT_FOUND, "Resource not found", 404),
    (Code.ALREADY_EXISTS, "Resource already exists", 409),
    (Code.PERMISSION_DENIED, "Permission denied", 403),
    (Code.RESOURCE_EXHAUSTED, "Resource exhausted", 429),
    (Code.FAILED_PRECONDITION, "Failed precondition", 400),
    (Code.ABORTED, "Operation aborted", 409),
    (Code.OUT_OF_RANGE, "Out of range", 400),
    (Code.UNIMPLEMENTED, "Method not implemented", 501),
    (Code.INTERNAL, "Internal server error", 500),
    (Code.UNAVAILABLE, "Service unavailable", 503),
    (Code.DATA_LOSS, "Data loss occurred", 500),
    (Code.UNAUTHENTICATED, "Unauthenticated access", 401),
]


@pytest.mark.parametrize("code,message,http_status", _errors)
def test_sync_errors(
    code: Code,
    message: str,
    http_status: int,
):
    class ErrorHaberdasherSync(HaberdasherSync):
        def __init__(self, exception: ConnecpyException):
            self._exception = exception

        def MakeHat(self, request, ctx):
            raise self._exception

    haberdasher = ErrorHaberdasherSync(ConnecpyException(code, message))
    app = HaberdasherWSGIApplication(haberdasher)
    transport = WSGITransport(app)

    recorded_response: Optional[Response] = None

    def record_response(response):
        nonlocal recorded_response
        recorded_response = response

    session = Client(transport=transport, event_hooks={"response": [record_response]})

    with (
        HaberdasherClientSync("http://localhost", session=session) as client,
        pytest.raises(ConnecpyException) as exc_info,
    ):
        client.MakeHat(request=Size(inches=10))

    assert exc_info.value.code == code
    assert exc_info.value.message == message
    assert recorded_response is not None
    assert recorded_response.status_code == http_status


@pytest.mark.asyncio
@pytest.mark.parametrize("code,message,http_status", _errors)
async def test_async_errors(
    code: Code,
    message: str,
    http_status: int,
):
    class ErrorHaberdasher(Haberdasher):
        def __init__(self, exception: ConnecpyException):
            self._exception = exception

        async def MakeHat(self, request, ctx):
            raise self._exception

    haberdasher = ErrorHaberdasher(ConnecpyException(code, message))
    app = HaberdasherASGIApplication(haberdasher)
    transport = ASGITransport(app)  # pyright:ignore[reportArgumentType] - httpx type is not complete

    recorded_response: Optional[Response] = None

    async def record_response(response):
        nonlocal recorded_response
        recorded_response = response

    async with (
        AsyncClient(
            transport=transport, event_hooks={"response": [record_response]}
        ) as session,
        HaberdasherClient("http://localhost", session=session) as client,
    ):
        with pytest.raises(ConnecpyException) as exc_info:
            await client.MakeHat(request=Size(inches=10))

    assert exc_info.value.code == code
    assert exc_info.value.message == message
    assert recorded_response is not None
    assert recorded_response.status_code == http_status


_http_errors = [
    p(400, {}, Code.INTERNAL, "Bad Request", id="400"),
    p(401, {}, Code.UNAUTHENTICATED, "Unauthorized", id="401"),
    p(403, {}, Code.PERMISSION_DENIED, "Forbidden", id="403"),
    p(404, {}, Code.UNIMPLEMENTED, "Not Found", id="404"),
    p(429, {}, Code.UNAVAILABLE, "Too Many Requests", id="429"),
    p(499, {}, Code.UNKNOWN, "Client Closed Request", id="499"),
    p(502, {}, Code.UNAVAILABLE, "Bad Gateway", id="502"),
    p(503, {}, Code.UNAVAILABLE, "Service Unavailable", id="503"),
    p(504, {}, Code.UNAVAILABLE, "Gateway Timeout", id="504"),
    p(
        400,
        {"json": {"code": "invalid_argument", "message": "Bad parameter"}},
        Code.INVALID_ARGUMENT,
        "Bad parameter",
        id="connect error",
    ),
    p(
        400,
        {"json": {"message": "Bad parameter"}},
        Code.INTERNAL,
        "Bad parameter",
        id="connect error without code",
    ),
    p(
        404,
        {"json": {"code": "not_found"}},
        Code.NOT_FOUND,
        "",
        id="connect error without message",
    ),
    p(
        502,
        {"text": '"{bad_json'},
        Code.UNAVAILABLE,
        "Bad Gateway",
        id="bad json",
    ),
    p(
        200,
        {"text": "weird encoding", "headers": {"content-encoding": "weird"}},
        Code.INTERNAL,
        "unknown encoding 'weird'; accepted encodings are gzip, br, zstd, identity",
        id="bad encoding",
    ),
]


@pytest.mark.parametrize("response_status,response_kwargs,code,message", _http_errors)
def test_sync_http_errors(response_status, response_kwargs, code, message):
    transport = MockTransport(lambda _: Response(response_status, **response_kwargs))
    with (
        HaberdasherClientSync(
            "http://localhost", session=Client(transport=transport)
        ) as client,
        pytest.raises(ConnecpyException) as exc_info,
    ):
        client.MakeHat(request=Size(inches=10))
    assert exc_info.value.code == code
    assert exc_info.value.message == message


@pytest.mark.asyncio
@pytest.mark.parametrize("response_status,response_kwargs,code,message", _http_errors)
async def test_async_http_errors(response_status, response_kwargs, code, message):
    transport = MockTransport(lambda _: Response(response_status, **response_kwargs))
    async with HaberdasherClient(
        "http://localhost", session=AsyncClient(transport=transport)
    ) as client:
        with pytest.raises(ConnecpyException) as exc_info:
            await client.MakeHat(request=Size(inches=10))
    assert exc_info.value.code == code
    assert exc_info.value.message == message


_client_errors = [
    p(
        "PUT",
        "/i2y.connecpy.example.Haberdasher/MakeHat",
        {"Content-Type": "application/proto"},
        Size(inches=10).SerializeToString(),
        HTTPStatus.METHOD_NOT_ALLOWED,
        {"Allow": "GET, POST"},
        id="bad method",
    ),
    p(
        "POST",
        "/notservicemethod",
        {"Content-Type": "application/proto"},
        Size(inches=10).SerializeToString(),
        HTTPStatus.NOT_FOUND,
        {},
        id="not found",
    ),
    p(
        "POST",
        "/notservice/method",
        {"Content-Type": "application/proto"},
        Size(inches=10).SerializeToString(),
        HTTPStatus.NOT_FOUND,
        {},
        id="not present service",
    ),
    p(
        "POST",
        "/i2y.connecpy.example.Haberdasher/notmethod",
        {"Content-Type": "application/proto"},
        Size(inches=10).SerializeToString(),
        HTTPStatus.NOT_FOUND,
        {},
        id="not present method",
    ),
    p(
        "POST",
        "/i2y.connecpy.example.Haberdasher/MakeHat",
        {"Content-Type": "text/html"},
        Size(inches=10).SerializeToString(),
        HTTPStatus.UNSUPPORTED_MEDIA_TYPE,
        {"Accept-Post": "application/json, application/proto"},
        id="bad content type",
    ),
    p(
        "POST",
        "/i2y.connecpy.example.Haberdasher/MakeHat",
        {"Content-Type": "application/proto", "connect-protocol-version": "2"},
        Size(inches=10).SerializeToString(),
        HTTPStatus.BAD_REQUEST,
        {"content-type": "application/json"},
        id="bad connect protocol version",
    ),
]


@pytest.mark.parametrize(
    "method,path,headers,body,response_status,response_headers", _client_errors
)
def test_sync_client_errors(
    method, path, headers, body, response_status, response_headers
):
    class ValidHaberdasherSync(HaberdasherSync):
        def MakeHat(self, request, ctx):
            return Hat()

    app = HaberdasherWSGIApplication(ValidHaberdasherSync())
    transport = WSGITransport(app)

    client = Client(transport=transport)
    response = client.request(
        method=method,
        url=f"http://localhost{path}",
        content=body,
        headers=headers,
    )

    assert response.status_code == response_status
    assert response.headers == response_headers


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "method,path,headers,body,response_status,response_headers", _client_errors
)
async def test_async_client_errors(
    method, path, headers, body, response_status, response_headers
):
    class ValidHaberdasher(Haberdasher):
        async def MakeHat(self, request, ctx):
            return Hat()

    haberdasher = ValidHaberdasher()
    app = HaberdasherASGIApplication(haberdasher)
    transport = ASGITransport(app)  # pyright:ignore[reportArgumentType] - httpx type is not complete

    client = AsyncClient(transport=transport)
    response = await client.request(
        method=method,
        url=f"http://localhost{path}",
        content=body,
        headers=headers,
    )

    assert response.status_code == response_status
    assert response.headers == response_headers


# To exercise timeouts, can't use mock transports
@pytest.fixture(scope="module")
def sync_timeout_server():
    class SleepingHaberdasherSync(HaberdasherSync):
        def MakeHat(self, request, ctx):
            time.sleep(10)
            raise AssertionError("Should be timedout already")

    app = HaberdasherWSGIApplication(SleepingHaberdasherSync())

    with make_server("", 0, app) as httpd:
        thread = threading.Thread(target=httpd.serve_forever)
        thread.daemon = True
        thread.start()
        try:
            yield httpd
        finally:
            # Don't wait for sleeping server to shutdown cleanly for this
            # test, we don't care anyways.
            pass


@pytest.mark.parametrize(
    "client_timeout_ms, call_timeout_ms",
    (
        (1, None),
        (None, 1),
    ),
)
def test_sync_client_timeout(
    client_timeout_ms, call_timeout_ms, sync_timeout_server: WSGIServer
):
    recorded_timeout_header = ""

    def modify_timeout_header(request: Request):
        nonlocal recorded_timeout_header
        recorded_timeout_header = request.headers.get("connect-timeout-ms")
        # Make sure server doesn't timeout since we are verifying client timeout
        request.headers["connect-timeout-ms"] = "10000"

    with (
        Client(
            timeout=Timeout(
                None,
                read=client_timeout_ms / 1000.0
                if client_timeout_ms is not None
                else None,
            ),
            event_hooks={"request": [modify_timeout_header]},
        ) as session,
        HaberdasherClientSync(
            f"http://localhost:{sync_timeout_server.server_port}",
            timeout_ms=client_timeout_ms,
            session=session,
        ) as client,
        pytest.raises(ConnecpyException) as exc_info,
    ):
        client.MakeHat(request=Size(inches=10), timeout_ms=call_timeout_ms)

    assert exc_info.value.code == Code.DEADLINE_EXCEEDED
    assert exc_info.value.message == "Request timed out"
    assert recorded_timeout_header == "1"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "client_timeout_ms, call_timeout_ms",
    (
        (1, None),
        (None, 1),
    ),
)
async def test_async_client_timeout(
    client_timeout_ms, call_timeout_ms, sync_timeout_server: WSGIServer
):
    recorded_timeout_header = ""

    async def modify_timeout_header(request: Request):
        nonlocal recorded_timeout_header
        recorded_timeout_header = request.headers.get("connect-timeout-ms")
        # Make sure server doesn't timeout since we are verifying client timeout
        request.headers["connect-timeout-ms"] = "10000"

    async with (
        AsyncClient(
            timeout=Timeout(None), event_hooks={"request": [modify_timeout_header]}
        ) as session,
        HaberdasherClient(
            f"http://localhost:{sync_timeout_server.server_port}",
            timeout_ms=client_timeout_ms,
            session=session,
        ) as client,
    ):
        with pytest.raises(ConnecpyException) as exc_info:
            await client.MakeHat(request=Size(inches=10), timeout_ms=call_timeout_ms)

    assert exc_info.value.code == Code.DEADLINE_EXCEEDED
    assert exc_info.value.message == "Request timed out"
    assert recorded_timeout_header == "1"
