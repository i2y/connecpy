import argparse
import asyncio
import os
import ssl
import sys
from tempfile import TemporaryFile
from typing import Literal

import httpx
from _util import create_standard_streams
from connecpy.client import ResponseMetadata
from connecpy.code import Code
from connecpy.exceptions import ConnecpyException
from connecpy.headers import Headers
from connectrpc.conformance.v1.client_compat_pb2 import (
    ClientCompatRequest,
    ClientCompatResponse,
)
from connectrpc.conformance.v1.config_pb2 import Code as ConformanceCode
from connectrpc.conformance.v1.config_pb2 import Codec, Compression, HTTPVersion
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


def _convert_code(error: Code) -> ConformanceCode:
    match error:
        case Code.CANCELED:
            return ConformanceCode.CODE_CANCELED
        case Code.UNKNOWN:
            return ConformanceCode.CODE_UNKNOWN
        case Code.INVALID_ARGUMENT:
            return ConformanceCode.CODE_INVALID_ARGUMENT
        case Code.DEADLINE_EXCEEDED:
            return ConformanceCode.CODE_DEADLINE_EXCEEDED
        case Code.NOT_FOUND:
            return ConformanceCode.CODE_NOT_FOUND
        case Code.ALREADY_EXISTS:
            return ConformanceCode.CODE_ALREADY_EXISTS
        case Code.PERMISSION_DENIED:
            return ConformanceCode.CODE_PERMISSION_DENIED
        case Code.RESOURCE_EXHAUSTED:
            return ConformanceCode.CODE_RESOURCE_EXHAUSTED
        case Code.FAILED_PRECONDITION:
            return ConformanceCode.CODE_FAILED_PRECONDITION
        case Code.ABORTED:
            return ConformanceCode.CODE_ABORTED
        case Code.OUT_OF_RANGE:
            return ConformanceCode.CODE_OUT_OF_RANGE
        case Code.UNIMPLEMENTED:
            return ConformanceCode.CODE_UNIMPLEMENTED
        case Code.INTERNAL:
            return ConformanceCode.CODE_INTERNAL
        case Code.UNAVAILABLE:
            return ConformanceCode.CODE_UNAVAILABLE
        case Code.DATA_LOSS:
            return ConformanceCode.CODE_DATA_LOSS
        case Code.UNAUTHENTICATED:
            return ConformanceCode.CODE_UNAUTHENTICATED


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

    request_headers = Headers()
    for header in test_request.request_headers:
        for value in header.value:
            request_headers.add(header.name, value)
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
            except ConnecpyException as e:
                test_response.response.error.code = _convert_code(e.code)
                test_response.response.error.message = e.message
                test_response.response.error.details.extend(e.details)
            except Exception as e:
                test_response.error.message = str(e)

            for name in meta.headers().keys():
                test_response.response.response_headers.add(
                    name=name, value=meta.headers().getall(name)
                )
            for name in meta.trailers().keys():
                test_response.response.response_trailers.add(
                    name=name, value=meta.trailers().getall(name)
                )

    return test_response


class Args(argparse.Namespace):
    mode: Literal["sync", "async"]


async def main():
    parser = argparse.ArgumentParser(description="Conformance client")
    parser.add_argument("--mode", choices=["sync", "async"])
    args = parser.parse_args(namespace=Args())

    stdin, stdout = await create_standard_streams()
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
    if os.environ.get("CI") and sys.platform == "darwin":
        # Use uvloop on macOS in CI because the asyncio implementation seems to
        # cause some flakiness with timing-related tests.
        import uvloop

        uvloop.run(main())
    else:
        asyncio.run(main())
