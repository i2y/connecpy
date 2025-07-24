import argparse
import asyncio
import sys
from collections.abc import Coroutine
from typing import Any, Literal

import httpx
from connecpy.client import ResponseMetadata
from connecpy.errors import Errors
from connecpy.exceptions import ConnecpyServerException
from connectrpc.conformance.v1.config_pb2 import Code
from connectrpc.conformance.v1.client_compat_pb2 import (
    ClientCompatRequest,
    ClientCompatResponse,
)
from connectrpc.conformance.v1.service_pb2 import (
    IdempotentUnaryRequest,
    IdempotentUnaryResponse,
    UnaryRequest,
    UnaryResponse,
    UnimplementedRequest,
)
from connectrpc.conformance.v1.service_connecpy import ConformanceServiceClientSync, ConformanceServiceClient


def _convert_code(error: Errors) -> Code:
    match error:
        case Errors.Canceled:
            return Code.CODE_CANCELED
        case Errors.Unknown:
            return Code.CODE_UNKNOWN
        case Errors.InvalidArgument:
            return Code.CODE_INVALID_ARGUMENT
        case Errors.DeadlineExceeded:
            return Code.CODE_DEADLINE_EXCEEDED
        case Errors.NotFound:
            return Code.CODE_NOT_FOUND
        case Errors.AlreadyExists:
            return Code.CODE_ALREADY_EXISTS
        case Errors.PermissionDenied:
            return Code.CODE_PERMISSION_DENIED
        case Errors.ResourceExhausted:
            return Code.CODE_RESOURCE_EXHAUSTED
        case Errors.FailedPrecondition:
            return Code.CODE_FAILED_PRECONDITION
        case Errors.Aborted:
            return Code.CODE_ABORTED
        case Errors.OutOfRange:
            return Code.CODE_OUT_OF_RANGE
        case Errors.Unimplemented:
            return Code.CODE_UNIMPLEMENTED
        case Errors.Internal:
            return Code.CODE_INTERNAL
        case Errors.Unavailable:
            return Code.CODE_UNAVAILABLE
        case Errors.DataLoss:
            return Code.CODE_DATA_LOSS
        case Errors.Unauthenticated:
            return Code.CODE_UNAUTHENTICATED


async def _run_test(client: ConformanceServiceClientSync | ConformanceServiceClient, test_request: ClientCompatRequest) -> ClientCompatResponse:
    test_response = ClientCompatResponse()
    test_response.test_name = test_request.test_name

    timeout_ms = None
    if test_request.timeout_ms:
        timeout_ms = test_request.timeout_ms

    request_headers = []
    for header in test_request.request_headers:
        for value in header.value:
            request_headers.append((header.name, value))
    for message_any in test_request.request_messages:
        match test_request.method:
            case "IdempotentUnary":
                client_request = IdempotentUnaryRequest()
            case "Unary":
                client_request = UnaryRequest()
            case "Unimplemented":
                client_request = UnimplementedRequest()
            case _:
                test_response.error.message = "Unrecognized method"
                return test_response
        if not message_any.Unpack(client_request):
            raise ValueError("Failed to unpack message")
        with ResponseMetadata() as meta:
            try:
                task: asyncio.Task[IdempotentUnaryResponse | UnaryResponse]
                match client_request:
                    case IdempotentUnaryRequest():
                        if isinstance(client, ConformanceServiceClientSync):
                            task = asyncio.create_task(asyncio.to_thread(client.IdempotentUnary,
                                client_request,
                                headers=request_headers,
                                use_get=test_request.use_get_http_method,
                                timeout_ms=timeout_ms,
                            ))
                        else:
                            task = asyncio.create_task(client.IdempotentUnary(
                                client_request,
                                headers=request_headers,
                                use_get=test_request.use_get_http_method,
                                timeout_ms=timeout_ms,
                            ))
                    case UnaryRequest():
                        if isinstance(client, ConformanceServiceClientSync):
                            task = asyncio.create_task(asyncio.to_thread(client.Unary,
                                client_request,
                                headers=request_headers,
                                timeout_ms=timeout_ms,
                            ))
                        else:
                            task = asyncio.create_task(client.Unary(
                                client_request,
                                headers=request_headers,
                                timeout_ms=timeout_ms,
                            ))
                    case UnimplementedRequest():
                        if isinstance(client, ConformanceServiceClientSync):
                            await asyncio.to_thread(client.Unimplemented,
                                client_request,
                                headers=request_headers,
                                timeout_ms=timeout_ms,
                            )
                        else:
                            await client.Unimplemented(
                                client_request,
                                headers=request_headers,
                                timeout_ms=timeout_ms,
                            )
                        raise ValueError("Can't happen")
                if test_request.HasField('cancel'):
                    await asyncio.sleep(test_request.cancel.after_close_send_ms / 1000.0)
                    task.cancel()
                client_response = await task
                test_response.response.payloads.add().MergeFrom(
                    client_response.payload
                )
            except ConnecpyServerException as e:
                test_response.response.error.code = _convert_code(e.code)
                test_response.response.error.message = e.message
                test_response.response.error.details.extend(e.details)
            except Exception as e:
                test_response.error.message = str(e)

            for name in meta.headers().keys():
                test_response.response.response_headers.add(
                    name=name, value=meta.headers().get_list(name)
                )
            for name in meta.trailers().keys():
                test_response.response.response_trailers.add(
                    name=name, value=meta.trailers().get_list(name)
                    )

    return test_response


async def _create_standard_streams():
    loop = asyncio.get_event_loop()
    stdin = asyncio.StreamReader()
    protocol = asyncio.StreamReaderProtocol(stdin)
    await loop.connect_read_pipe(lambda: protocol, sys.stdin)
    w_transport, w_protocol = await loop.connect_write_pipe(
        asyncio.streams.FlowControlMixin, sys.stdout
    )
    stdout = asyncio.StreamWriter(w_transport, w_protocol, stdin, loop)
    return stdin, stdout


class Args(argparse.Namespace):
    mode: Literal["sync"] | Literal["async"]

async def main():
    parser = argparse.ArgumentParser(description="Conformance client")
    parser.add_argument("--mode", choices=["sync", "async"])
    args = parser.parse_args(namespace=Args())

    async with httpx.AsyncClient() as async_session:
        with httpx.Client() as sync_session:
            stdin, stdout = await _create_standard_streams()
            while True:
                try:
                    size_buf = await stdin.readexactly(4)
                except asyncio.IncompleteReadError:
                    return
                size = int.from_bytes(size_buf)
                # Allow to raise even on EOF since we always should have a message
                request_buf = await stdin.readexactly(size)
                request = ClientCompatRequest()
                request.ParseFromString(request_buf)

                match args.mode:
                    case "sync":
                        with ConformanceServiceClientSync(f"http://{request.host}:{request.port}", session=sync_session) as client:
                            response = await _run_test(client, request)
                    case "async":
                        async with ConformanceServiceClient(f"http://{request.host}:{request.port}", session=async_session) as client:
                            response = await _run_test(client, request)

                response_buf = response.SerializeToString()
                size_buf = len(response_buf).to_bytes(4)
                stdout.write(size_buf)
                stdout.write(response_buf)
                await stdout.drain()


if __name__ == "__main__":
    asyncio.run(main())
