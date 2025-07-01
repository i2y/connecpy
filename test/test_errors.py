from httpx import (
    ASGITransport,
    AsyncClient,
    Client,
    Response,
    WSGITransport,
)
import pytest
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
from example.haberdasher_pb2 import Size
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
    # Custom error codes not defined by Connect
    (Errors.BadRoute, "Bad route", 404),
    (Errors.Malformed, "Malformed request", 400),
]


class ErrorHaberdasherSync(HaberdasherSync):
    def __init__(self, exception: ConnecpyServerException):
        self._exception = exception

    def MakeHat(self, _req, _ctx):
        raise self._exception

    def DoNothing(self, _req, _ctx):
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

    recorded_response: Response = None

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
    assert recorded_response.status_code == http_status


class ErrorHaberdasher(Haberdasher):
    def __init__(self, exception: ConnecpyServerException):
        self._exception = exception

    async def MakeHat(self, _req, _ctx):
        raise self._exception

    async def DoNothing(self, _req, _ctx):
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

    recorded_response: Response = None

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
    assert recorded_response.status_code == http_status
