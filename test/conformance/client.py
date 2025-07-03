import sys
import time
from typing import BinaryIO

import httpx
from connecpy.context import ClientContext
from connecpy.errors import Errors
from connecpy.exceptions import ConnecpyServerException
from connectrpc.conformance.v1.config_pb2 import Code
from connectrpc.conformance.v1.client_compat_pb2 import (
    ClientCompatRequest,
    ClientCompatResponse,
)
from connectrpc.conformance.v1.service_pb2 import UnaryRequest
from connectrpc.conformance.v1.service_connecpy import ConformanceServiceClient


def _readexactly(stream: BinaryIO, n: int) -> bytes:
    buf = b""
    while len(buf) < n:
        chunk = stream.read(n - len(buf))
        if not chunk:
            raise EOFError("Unexpected end of file")
        buf += chunk
    return buf


def _convert_code(error: Errors) -> Code:
    if error == Errors.Canceled:
        return Code.CODE_CANCELED
    if error == Errors.Unknown:
        return Code.CODE_UNKNOWN
    if error == Errors.InvalidArgument:
        return Code.CODE_INVALID_ARGUMENT
    if error == Errors.DeadlineExceeded:
        return Code.CODE_DEADLINE_EXCEEDED
    if error == Errors.NotFound:
        return Code.CODE_NOT_FOUND
    if error == Errors.AlreadyExists:
        return Code.CODE_ALREADY_EXISTS
    if error == Errors.PermissionDenied:
        return Code.CODE_PERMISSION_DENIED
    if error == Errors.ResourceExhausted:
        return Code.CODE_RESOURCE_EXHAUSTED
    if error == Errors.FailedPrecondition:
        return Code.CODE_FAILED_PRECONDITION
    if error == Errors.Aborted:
        return Code.CODE_ABORTED
    if error == Errors.OutOfRange:
        return Code.CODE_OUT_OF_RANGE
    if error == Errors.Unimplemented:
        return Code.CODE_UNIMPLEMENTED
    if error == Errors.Internal:
        return Code.CODE_INTERNAL
    if error == Errors.Unavailable:
        return Code.CODE_UNAVAILABLE
    if error == Errors.DataLoss:
        return Code.CODE_DATA_LOSS
    if error == Errors.Unauthenticated:
        return Code.CODE_UNAUTHENTICATED



def _run_test_sync(test_request: ClientCompatRequest) -> ClientCompatResponse:
    test_response = ClientCompatResponse()
    test_response.test_name = test_request.test_name

    if test_request.request_delay_ms:
        time.sleep(test_request.request_delay_ms / 1000.0)

    request_headers = {h.name: h.value[0] for h in test_request.request_headers}

    http_response: httpx.Response = httpx.Response(status_code=200)

    def record_response(resp: httpx.Response) -> None:
        nonlocal http_response
        http_response = resp

    timeout = 60
    if test_request.timeout_ms:
        timeout = int(test_request.timeout_ms / 1000.0)

    with (
        httpx.Client(
            event_hooks={"response": [record_response]},
        ) as session,
        ConformanceServiceClient(
            f"http://{test_request.host}:{test_request.port}", session=session, timeout=timeout,
        ) as client,
    ):
        if test_request.method == "Unary":
            for message_any in test_request.request_messages:
                client_request = UnaryRequest()
                if not message_any.Unpack(client_request):
                    raise ValueError("Failed to unpack message")
                try:
                    client_response = client.Unary(
                        client_request, ctx=ClientContext(headers=request_headers)
                    )
                    test_response.response.payloads.add().MergeFrom(client_response.payload)
                except ConnecpyServerException as e:
                    test_response.response.error.code = _convert_code(e.code)
                    test_response.response.error.message = e.message
                except Exception:
                    pass
                for header, value in http_response.headers.items():
                    test_response.response.response_headers.add(
                        name=header, value=[value]
                    )

    return test_response


def main():
    while True:
        try:
            size_buf = _readexactly(sys.stdin.buffer, 4)
        except EOFError:
            return
        size = int.from_bytes(size_buf)
        # Allow to raise since we always should have a message
        request_buf = _readexactly(sys.stdin.buffer, size)
        request = ClientCompatRequest()
        request.ParseFromString(request_buf)

        response = _run_test_sync(request)

        response_buf = response.SerializeToString()
        size_buf = len(response_buf).to_bytes(4)
        sys.stdout.buffer.write(size_buf)
        sys.stdout.buffer.write(response_buf)
        sys.stdout.buffer.flush()


if __name__ == "__main__":
    main()
