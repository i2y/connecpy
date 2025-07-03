from http import HTTPMethod, HTTPStatus
from typing import Optional

from httpx import (
    ASGITransport,
    AsyncClient,
    Client,
    Response,
    MockTransport,
    WSGITransport,
)
import pytest
from pytest import param as p
from connecpy.asgi import ConnecpyASGIApp
from connecpy.errors import Errors
from connecpy.exceptions import ConnecpyServerException
from connecpy.wsgi import ConnecpyWSGIApp
from example.haberdasher_connecpy import (
    AsyncHaberdasherClient,
    Haberdasher,
    HaberdasherServer,
    HaberdasherSync,
    HaberdasherServerSync,
    HaberdasherClient,
)
from example.haberdasher_pb2 import Hat, Size
from google.protobuf.empty_pb2 import Empty


_errors = [
    (Errors.Canceled, "Operation was cancelled", 499),
    (Errors.Unknown, "An unknown error occurred", 500),
    (Errors.InvalidArgument, "That's not right", 400),
    (Errors.DeadlineExceeded, "Deadline exceeded", 504),
    (Errors.NotFound, "Resource not found", 404),
    (Errors.AlreadyExists, "Resource already exists", 409),
    (Errors.PermissionDenied, "Permission denied", 403),
    (Errors.ResourceExhausted, "Resource exhausted", 429),
    (Errors.FailedPrecondition, "Failed precondition", 400),
    (Errors.Aborted, "Operation aborted", 409),
    (Errors.OutOfRange, "Out of range", 400),
    (Errors.Unimplemented, "Method not implemented", 501),
    (Errors.Internal, "Internal server error", 500),
    (Errors.Unavailable, "Service unavailable", 503),
    (Errors.DataLoss, "Data loss occurred", 500),
    (Errors.Unauthenticated, "Unauthenticated access", 401),
]


class ErrorHaberdasherSync(HaberdasherSync):
    def __init__(self, exception: ConnecpyServerException):
        self._exception = exception

    def MakeHat(self, req, ctx):
        raise self._exception

    def DoNothing(self, req, ctx):
        return Empty()


@pytest.mark.parametrize("error,message,http_status", _errors)
def test_sync_errors(
    error: Errors,
    message: str,
    http_status: int,
):
    haberdasher = ErrorHaberdasherSync(
        ConnecpyServerException(
            code=error,
            message=message,
        )
    )
    server = HaberdasherServerSync(service=haberdasher)
    app = ConnecpyWSGIApp()
    app.add_service(server)
    transport = WSGITransport(app)

    recorded_response: Optional[Response] = None

    def record_response(response):
        nonlocal recorded_response
        recorded_response = response

    session = Client(transport=transport, event_hooks={"response": [record_response]})

    with (
        HaberdasherClient("http://localhost", session=session) as client,
        pytest.raises(ConnecpyServerException) as exc_info,
    ):
        client.MakeHat(request=Size(inches=10))

    assert exc_info.value.code == error
    assert exc_info.value.message == message
    assert recorded_response is not None
    assert recorded_response.status_code == http_status


class ErrorHaberdasher(Haberdasher):
    def __init__(self, exception: ConnecpyServerException):
        self._exception = exception

    async def MakeHat(self, req, ctx):
        raise self._exception

    async def DoNothing(self, req, ctx):
        return Empty()


@pytest.mark.asyncio
@pytest.mark.parametrize("error,message,http_status", _errors)
async def test_async_errors(
    error: Errors,
    message: str,
    http_status: int,
):
    haberdasher = ErrorHaberdasher(
        ConnecpyServerException(
            code=error,
            message=message,
        )
    )
    server = HaberdasherServer(service=haberdasher)
    app = ConnecpyASGIApp()
    app.add_service(server)
    transport = ASGITransport(app)

    recorded_response: Optional[Response] = None

    async def record_response(response):
        nonlocal recorded_response
        recorded_response = response

    async with (
        AsyncClient(
            transport=transport, event_hooks={"response": [record_response]}
        ) as session,
        AsyncHaberdasherClient("http://localhost", session=session) as client,
    ):
        with pytest.raises(ConnecpyServerException) as exc_info:
            await client.MakeHat(request=Size(inches=10))

    assert exc_info.value.code == error
    assert exc_info.value.message == message
    assert recorded_response is not None
    assert recorded_response.status_code == http_status


_http_errors = [
    p(400, {}, Errors.Internal, "Bad Request", id="400"),
    p(401, {}, Errors.Unauthenticated, "Unauthorized", id="401"),
    p(403, {}, Errors.PermissionDenied, "Forbidden", id="403"),
    p(404, {}, Errors.Unimplemented, "Not Found", id="404"),
    p(429, {}, Errors.Unavailable, "Too Many Requests", id="429"),
    p(499, {}, Errors.Unknown, "Client Closed Request", id="499"),
    p(502, {}, Errors.Unavailable, "Bad Gateway", id="502"),
    p(503, {}, Errors.Unavailable, "Service Unavailable", id="503"),
    p(504, {}, Errors.Unavailable, "Gateway Timeout", id="504"),
    p(
        400,
        {"json": {"code": "invalid_argument", "message": "Bad parameter"}},
        Errors.InvalidArgument,
        "Bad parameter",
        id="connect error",
    ),
    p(
        400,
        {"json": {"message": "Bad parameter"}},
        Errors.Internal,
        "Bad parameter",
        id="connect error without code",
    ),
    p(
        404,
        {"json": {"code": "not_found"}},
        Errors.NotFound,
        "",
        id="connect error without message",
    ),
    p(
        502,
        {"text": '"{bad_json'},
        Errors.Unavailable,
        "Bad Gateway",
        id="bad json",
    ),
]


@pytest.mark.parametrize("response_status,response_kwargs,error,message", _http_errors)
def test_sync_http_errors(response_status, response_kwargs, error, message):
    transport = MockTransport(lambda _: Response(response_status, **response_kwargs))
    with (
        HaberdasherClient(
            "http://localhost", session=Client(transport=transport)
        ) as client,
        pytest.raises(ConnecpyServerException) as exc_info,
    ):
        client.MakeHat(request=Size(inches=10))
    assert exc_info.value.code == error
    assert exc_info.value.message == message


@pytest.mark.asyncio
@pytest.mark.parametrize("response_status,response_kwargs,error,message", _http_errors)
async def test_async_http_errors(response_status, response_kwargs, error, message):
    transport = MockTransport(lambda _: Response(response_status, **response_kwargs))
    async with AsyncHaberdasherClient(
        "http://localhost", session=AsyncClient(transport=transport)
    ) as client:
        with pytest.raises(ConnecpyServerException) as exc_info:
            await client.MakeHat(request=Size(inches=10))
    assert exc_info.value.code == error
    assert exc_info.value.message == message


_client_errors = [
    p(
        HTTPMethod.PUT,
        "/i2y.connecpy.example.Haberdasher/MakeHat",
        {"Content-Type": "application/proto"},
        Size(inches=10).SerializeToString(),
        HTTPStatus.METHOD_NOT_ALLOWED,
        {"Allow": "GET, POST"},
        id="bad method",
    ),
    p(
        HTTPMethod.POST,
        "/notservicemethod",
        {"Content-Type": "application/proto"},
        Size(inches=10).SerializeToString(),
        HTTPStatus.NOT_FOUND,
        {},
        id="not found",
    ),
    p(
        HTTPMethod.POST,
        "/notservice/method",
        {"Content-Type": "application/proto"},
        Size(inches=10).SerializeToString(),
        HTTPStatus.NOT_FOUND,
        {},
        id="not present service",
    ),
    p(
        HTTPMethod.POST,
        "/i2y.connecpy.example.Haberdasher/notmethod",
        {"Content-Type": "application/proto"},
        Size(inches=10).SerializeToString(),
        HTTPStatus.NOT_FOUND,
        {},
        id="not present method",
    ),
    p(
        HTTPMethod.POST,
        "/i2y.connecpy.example.Haberdasher/MakeHat",
        {"Content-Type": "text/html"},
        Size(inches=10).SerializeToString(),
        HTTPStatus.UNSUPPORTED_MEDIA_TYPE,
        {"Accept-Post": "application/json, application/proto"},
        id="bad content type",
    ),
    p(
        HTTPMethod.POST,
        "/i2y.connecpy.example.Haberdasher/MakeHat",
        {"Content-Type": "application/proto", "connect-protocol-version": "2"},
        Size(inches=10).SerializeToString(),
        HTTPStatus.BAD_REQUEST,
        {"content-type": "application/json"},
        id="bad connect protocol version",
    ),
]


class ValidHaberdasherSync(HaberdasherSync):
    def MakeHat(self, req, ctx):
        return Hat()

    def DoNothing(self, req, ctx):
        return Empty()


@pytest.mark.parametrize(
    "method,path,headers,body,response_status,response_headers", _client_errors
)
def test_sync_client_errors(
    method, path, headers, body, response_status, response_headers
):
    haberdasher = ValidHaberdasherSync()
    server = HaberdasherServerSync(service=haberdasher)
    app = ConnecpyWSGIApp()
    app.add_service(server)
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


class ValidHaberdasher(Haberdasher):
    async def MakeHat(self, req, ctx):
        return Hat()

    async def DoNothing(self, req, ctx):
        return Empty()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "method,path,headers,body,response_status,response_headers", _client_errors
)
async def test_async_client_errors(
    method, path, headers, body, response_status, response_headers
):
    haberdasher = ValidHaberdasher()
    server = HaberdasherServer(service=haberdasher)
    app = ConnecpyASGIApp()
    app.add_service(server)
    transport = ASGITransport(app)

    client = AsyncClient(transport=transport)
    response = await client.request(
        method=method,
        url=f"http://localhost{path}",
        content=body,
        headers=headers,
    )

    assert response.status_code == response_status
    assert response.headers == response_headers
