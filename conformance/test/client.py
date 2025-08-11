import argparse
import asyncio
import ssl
import time
from tempfile import NamedTemporaryFile
from typing import AsyncIterator, Iterator, Literal, TypeVar

import httpx
from _util import create_standard_streams
from connecpy.client import ResponseMetadata
from connecpy.code import Code
from connecpy.exceptions import ConnecpyException
from connecpy.request import Headers
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
    BidiStreamRequest,
    ClientStreamRequest,
    ConformancePayload,
    IdempotentUnaryRequest,
    ServerStreamRequest,
    UnaryRequest,
    UnimplementedRequest,
)
from google.protobuf.any import Any
from google.protobuf.message import Message


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


T = TypeVar("T", bound=Message)


def _unpack_request(message: Any, request: T) -> T:
    message.Unpack(request)
    return request


async def _run_test(
    mode: Literal["sync", "async"],
    test_request: ClientCompatRequest,
) -> ClientCompatResponse:
    test_response = ClientCompatResponse()
    test_response.test_name = test_request.test_name

    timeout_ms = None
    if test_request.timeout_ms:
        timeout_ms = test_request.timeout_ms
    read_max_bytes = None
    if test_request.message_receive_limit:
        read_max_bytes = test_request.message_receive_limit

    request_headers = Headers()
    for header in test_request.request_headers:
        for value in header.value:
            request_headers.add(header.name, value)

    payloads: list[ConformancePayload] = []

    with ResponseMetadata() as meta:
        try:
            task: asyncio.Task
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
                    with (
                        NamedTemporaryFile(delete_on_close=False) as cert_file,
                        NamedTemporaryFile(delete_on_close=False) as key_file,
                    ):
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
                            read_max_bytes=read_max_bytes,
                        ) as client,
                    ):
                        match test_request.method:
                            case "BidiStream":

                                def send_bidi_stream_request_sync(
                                    client: ConformanceServiceClientSync,
                                    request: Iterator[BidiStreamRequest],
                                ):
                                    for message in client.BidiStream(
                                        request,
                                        headers=request_headers,
                                        timeout_ms=timeout_ms,
                                    ):
                                        payloads.append(message.payload)
                                        if (
                                            num
                                            := test_request.cancel.after_num_responses
                                        ):
                                            if len(payloads) >= num:
                                                task.cancel()

                                def bidi_request_stream_sync():
                                    for message in test_request.request_messages:
                                        if test_request.request_delay_ms:
                                            time.sleep(
                                                test_request.request_delay_ms / 1000.0
                                            )
                                        yield _unpack_request(
                                            message, BidiStreamRequest()
                                        )

                                task = asyncio.create_task(
                                    asyncio.to_thread(
                                        send_bidi_stream_request_sync,
                                        client,
                                        bidi_request_stream_sync(),
                                    )
                                )

                            case "ClientStream":

                                def send_client_stream_request_sync(
                                    client: ConformanceServiceClientSync,
                                    request: Iterator[ClientStreamRequest],
                                ):
                                    res = client.ClientStream(
                                        request,
                                        headers=request_headers,
                                        timeout_ms=timeout_ms,
                                    )
                                    payloads.append(res.payload)

                                def request_stream_sync():
                                    for message in test_request.request_messages:
                                        if test_request.request_delay_ms:
                                            time.sleep(
                                                test_request.request_delay_ms / 1000.0
                                            )
                                        yield _unpack_request(
                                            message, ClientStreamRequest()
                                        )

                                task = asyncio.create_task(
                                    asyncio.to_thread(
                                        send_client_stream_request_sync,
                                        client,
                                        request_stream_sync(),
                                    )
                                )
                            case "IdempotentUnary":

                                def send_idempotent_unary_request_sync(
                                    client: ConformanceServiceClientSync,
                                    request: IdempotentUnaryRequest,
                                ):
                                    res = client.IdempotentUnary(
                                        request,
                                        headers=request_headers,
                                        use_get=test_request.use_get_http_method,
                                        timeout_ms=timeout_ms,
                                    )
                                    payloads.append(res.payload)

                                task = asyncio.create_task(
                                    asyncio.to_thread(
                                        send_idempotent_unary_request_sync,
                                        client,
                                        _unpack_request(
                                            test_request.request_messages[0],
                                            IdempotentUnaryRequest(),
                                        ),
                                    )
                                )
                            case "ServerStream":

                                def send_server_stream_request_sync(
                                    client: ConformanceServiceClientSync,
                                    request: ServerStreamRequest,
                                ):
                                    for message in client.ServerStream(
                                        request,
                                        headers=request_headers,
                                        timeout_ms=timeout_ms,
                                    ):
                                        payloads.append(message.payload)
                                        if (
                                            num
                                            := test_request.cancel.after_num_responses
                                        ):
                                            if len(payloads) >= num:
                                                task.cancel()

                                task = asyncio.create_task(
                                    asyncio.to_thread(
                                        send_server_stream_request_sync,
                                        client,
                                        _unpack_request(
                                            test_request.request_messages[0],
                                            ServerStreamRequest(),
                                        ),
                                    )
                                )
                            case "Unary":

                                def send_unary_request_sync(
                                    client: ConformanceServiceClientSync,
                                    request: UnaryRequest,
                                ):
                                    res = client.Unary(
                                        request,
                                        headers=request_headers,
                                        timeout_ms=timeout_ms,
                                    )
                                    payloads.append(res.payload)

                                task = asyncio.create_task(
                                    asyncio.to_thread(
                                        send_unary_request_sync,
                                        client,
                                        _unpack_request(
                                            test_request.request_messages[0],
                                            UnaryRequest(),
                                        ),
                                    )
                                )
                            case "Unimplemented":
                                task = asyncio.create_task(
                                    asyncio.to_thread(
                                        client.Unimplemented,
                                        _unpack_request(
                                            test_request.request_messages[0],
                                            UnimplementedRequest(),
                                        ),
                                        headers=request_headers,
                                        timeout_ms=timeout_ms,
                                    )
                                )
                            case _:
                                raise ValueError(
                                    f"Unrecognized method: {test_request.method}"
                                )
                        if test_request.cancel.after_close_send_ms:
                            await asyncio.sleep(
                                test_request.cancel.after_close_send_ms / 1000.0
                            )
                            task.cancel()
                        await task
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
                            read_max_bytes=read_max_bytes,
                        ) as client,
                    ):
                        match test_request.method:
                            case "BidiStream":

                                async def send_bidi_stream_request(
                                    client: ConformanceServiceClient,
                                    request: AsyncIterator[BidiStreamRequest],
                                ):
                                    responses = client.BidiStream(
                                        request,
                                        headers=request_headers,
                                        timeout_ms=timeout_ms,
                                    )
                                    async for response in responses:
                                        payloads.append(response.payload)
                                        if (
                                            num
                                            := test_request.cancel.after_num_responses
                                        ):
                                            if len(payloads) >= num:
                                                task.cancel()

                                async def bidi_stream_request():
                                    for message in test_request.request_messages:
                                        if test_request.request_delay_ms:
                                            await asyncio.sleep(
                                                test_request.request_delay_ms / 1000.0
                                            )
                                        yield _unpack_request(
                                            message, BidiStreamRequest()
                                        )
                                    if test_request.cancel.HasField(
                                        "before_close_send"
                                    ):
                                        task.cancel()
                                        # Don't finish the stream for this case by sleeping for
                                        # a long time. We won't end up sleeping for long since we
                                        # cancelled.
                                        await asyncio.sleep(600)

                                task = asyncio.create_task(
                                    send_bidi_stream_request(
                                        client, bidi_stream_request()
                                    )
                                )

                            case "ClientStream":

                                async def send_client_stream_request(
                                    client: ConformanceServiceClient,
                                    request: AsyncIterator[ClientStreamRequest],
                                ):
                                    res = await client.ClientStream(
                                        request,
                                        headers=request_headers,
                                        timeout_ms=timeout_ms,
                                    )
                                    payloads.append(res.payload)

                                async def client_stream_request():
                                    for message in test_request.request_messages:
                                        if test_request.request_delay_ms:
                                            await asyncio.sleep(
                                                test_request.request_delay_ms / 1000.0
                                            )
                                        yield _unpack_request(
                                            message, ClientStreamRequest()
                                        )
                                    if test_request.cancel.HasField(
                                        "before_close_send"
                                    ):
                                        task.cancel()
                                        # Don't finish the stream for this case by sleeping for
                                        # a long time. We won't end up sleeping for long since we
                                        # cancelled.
                                        await asyncio.sleep(600)

                                task = asyncio.create_task(
                                    send_client_stream_request(
                                        client,
                                        client_stream_request(),
                                    )
                                )
                            case "IdempotentUnary":

                                async def send_idempotent_unary_request(
                                    client: ConformanceServiceClient,
                                    request: IdempotentUnaryRequest,
                                ):
                                    res = await client.IdempotentUnary(
                                        request,
                                        headers=request_headers,
                                        use_get=test_request.use_get_http_method,
                                        timeout_ms=timeout_ms,
                                    )
                                    payloads.append(res.payload)

                                task = asyncio.create_task(
                                    send_idempotent_unary_request(
                                        client,
                                        _unpack_request(
                                            test_request.request_messages[0],
                                            IdempotentUnaryRequest(),
                                        ),
                                    )
                                )
                            case "ServerStream":

                                async def send_server_stream_request(
                                    client: ConformanceServiceClient,
                                    request: ServerStreamRequest,
                                ):
                                    async for message in client.ServerStream(
                                        request,
                                        headers=request_headers,
                                        timeout_ms=timeout_ms,
                                    ):
                                        payloads.append(message.payload)
                                        if (
                                            num
                                            := test_request.cancel.after_num_responses
                                        ):
                                            if len(payloads) >= num:
                                                task.cancel()

                                task = asyncio.create_task(
                                    send_server_stream_request(
                                        client,
                                        _unpack_request(
                                            test_request.request_messages[0],
                                            ServerStreamRequest(),
                                        ),
                                    )
                                )
                            case "Unary":

                                async def send_unary_request(
                                    client: ConformanceServiceClient,
                                    request: UnaryRequest,
                                ):
                                    res = await client.Unary(
                                        request,
                                        headers=request_headers,
                                        timeout_ms=timeout_ms,
                                    )
                                    payloads.append(res.payload)

                                task = asyncio.create_task(
                                    send_unary_request(
                                        client,
                                        _unpack_request(
                                            test_request.request_messages[0],
                                            UnaryRequest(),
                                        ),
                                    )
                                )
                            case "Unimplemented":
                                task = asyncio.create_task(
                                    client.Unimplemented(
                                        _unpack_request(
                                            test_request.request_messages[0],
                                            UnimplementedRequest(),
                                        ),
                                        headers=request_headers,
                                        timeout_ms=timeout_ms,
                                    )
                                )
                            case _:
                                raise ValueError(
                                    f"Unrecognized method: {test_request.method}"
                                )
                        if test_request.cancel.after_close_send_ms:
                            await asyncio.sleep(
                                test_request.cancel.after_close_send_ms / 1000.0
                            )
                            task.cancel()
                        await task
        except ConnecpyException as e:
            test_response.response.error.code = _convert_code(e.code)
            test_response.response.error.message = e.message
            test_response.response.error.details.extend(e.details)
        except (asyncio.CancelledError, Exception) as e:
            import sys
            import traceback

            traceback.print_tb(e.__traceback__, file=sys.stderr)
            test_response.error.message = str(e)

        test_response.response.payloads.extend(payloads)

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
    asyncio.run(main())
