import argparse
import asyncio
import ssl
import sys
from tempfile import TemporaryFile
from typing import Literal

import httpx
from connecpy.client import ResponseMetadata
from connecpy.errors import Errors
from connecpy.exceptions import ConnecpyServerException
from connectrpc.conformance.v1.client_compat_pb2 import (
    ClientCompatRequest,
    ClientCompatResponse,
)
from connectrpc.conformance.v1.config_pb2 import Code, Codec, Compression, HTTPVersion
from connectrpc.conformance.v1.service_connecpy import (
    ConformanceServiceClient,
    ConformanceServiceClientSync,
)
from connectrpc.conformance.v1.service_pb2 import (
    IdempotentUnaryRequest,
    IdempotentUnaryResponse,
    UnaryRequest,
    UnaryResponse,
    UnimplementedRequest,
)


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


def _convert_compression(compression: Compression) -> str:
    match compression:
        case Compression.COMPRESSION_IDENTITY:
            return "identity"
        case Compression.COMPRESSION_GZIP:
            return "gzip"
        case Compression.COMPRESSION_BR:
            return "br"
        case Compression.COMPRESSION_ZSTD:
            return "zstd"
        case Compression.COMPRESSION_DEFLATE:
            return "deflate"
        case Compression.COMPRESSION_SNAPPY:
            return "snappy"
        case _:
            raise ValueError(f"Unsupported compression: {compression}")


async def _run_test(
    mode: Literal["sync", "async"],
    test_request: ClientCompatRequest,
) -> ClientCompatResponse:
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
                session_kwargs = {}
                match test_request.http_version:
                    case HTTPVersion.HTTP_VERSION_1:
                        session_kwargs["http1"] = True
                        session_kwargs["http2"] = False
                    case HTTPVersion.HTTP_VERSION_2:
                        session_kwargs["http1"] = False
                        session_kwargs["http2"] = True
                scheme = "http"
                if test_request.server_tls_cert:
                    scheme = "https"
                    ctx = ssl.create_default_context(
                        purpose=ssl.Purpose.SERVER_AUTH,
                        cadata=test_request.server_tls_cert.decode(),
                    )
                    if test_request.HasField("client_tls_creds"):
                        with TemporaryFile() as cert_file, TemporaryFile() as key_file:
                            cert_file.write(test_request.client_tls_creds.cert)
                            cert_file.close()
                            key_file.write(test_request.client_tls_creds.key)
                            key_file.close()
                            ctx.load_cert_chain(
                                certfile=cert_file.name, keyfile=key_file.name
                            )
                    session_kwargs["verify"] = ctx
                match mode:
                    case "sync":
                        with (
                            httpx.Client(**session_kwargs) as session,
                            ConformanceServiceClientSync(
                                f"{scheme}://{test_request.host}:{test_request.port}",
                                session=session,
                                send_compression=_convert_compression(
                                    test_request.compression
                                ),
                                proto_json=test_request.codec == Codec.CODEC_JSON,
                            ) as client,
                        ):
                            match client_request:
                                case IdempotentUnaryRequest():
                                    task = asyncio.create_task(
                                        asyncio.to_thread(
                                            client.IdempotentUnary,
                                            client_request,
                                            headers=request_headers,
                                            use_get=test_request.use_get_http_method,
                                            timeout_ms=timeout_ms,
                                        )
                                    )
                                case UnaryRequest():
                                    task = asyncio.create_task(
                                        asyncio.to_thread(
                                            client.Unary,
                                            client_request,
                                            headers=request_headers,
                                            timeout_ms=timeout_ms,
                                        )
                                    )
                                case UnimplementedRequest():
                                    await asyncio.to_thread(
                                        client.Unimplemented,
                                        client_request,
                                        headers=request_headers,
                                        timeout_ms=timeout_ms,
                                    )
                                    raise ValueError("Can't happen")
                            if test_request.HasField("cancel"):
                                await asyncio.sleep(
                                    test_request.cancel.after_close_send_ms / 1000.0
                                )
                                task.cancel()
                            client_response = await task
                    case "async":
                        async with (
                            httpx.AsyncClient(**session_kwargs) as session,
                            ConformanceServiceClient(
                                f"{scheme}://{test_request.host}:{test_request.port}",
                                session=session,
                                send_compression=_convert_compression(
                                    test_request.compression
                                ),
                                proto_json=test_request.codec == Codec.CODEC_JSON,
                            ) as client,
                        ):
                            match client_request:
                                case IdempotentUnaryRequest():
                                    task = asyncio.create_task(
                                        client.IdempotentUnary(
                                            client_request,
                                            headers=request_headers,
                                            use_get=test_request.use_get_http_method,
                                            timeout_ms=timeout_ms,
                                        )
                                    )
                                case UnaryRequest():
                                    task = asyncio.create_task(
                                        client.Unary(
                                            client_request,
                                            headers=request_headers,
                                            timeout_ms=timeout_ms,
                                        )
                                    )
                                case UnimplementedRequest():
                                    await client.Unimplemented(
                                        client_request,
                                        headers=request_headers,
                                        timeout_ms=timeout_ms,
                                    )
                                    raise ValueError("Can't happen")
                            if test_request.HasField("cancel"):
                                await asyncio.sleep(
                                    test_request.cancel.after_close_send_ms / 1000.0
                                )
                                task.cancel()
                            client_response = await task
                test_response.response.payloads.add().MergeFrom(client_response.payload)
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

        response = await _run_test(args.mode, request)

        response_buf = response.SerializeToString()
        size_buf = len(response_buf).to_bytes(4)
        stdout.write(size_buf)
        stdout.write(response_buf)
        await stdout.drain()


if __name__ == "__main__":
    asyncio.run(main())
