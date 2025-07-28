import argparse
import asyncio
import signal
from contextlib import ExitStack
from tempfile import NamedTemporaryFile
from typing import Literal, TypeVar

from _util import create_standard_streams
from connecpy.code import Code
from connecpy.exceptions import ConnecpyServerException
from connecpy.server import ServiceContext
from connectrpc.conformance.v1.config_pb2 import Code as ConformanceCode
from connectrpc.conformance.v1.server_compat_pb2 import (
    ServerCompatRequest,
    ServerCompatResponse,
)
from connectrpc.conformance.v1.service_connecpy import (
    ConformanceService,
    ConformanceServiceASGIApplication,
    ConformanceServiceSync,
    ConformanceServiceWSGIApplication,
)
from connectrpc.conformance.v1.service_pb2 import (
    ConformancePayload,
    IdempotentUnaryRequest,
    IdempotentUnaryResponse,
    UnaryRequest,
    UnaryResponse,
    UnaryResponseDefinition,
)
from google.protobuf.any import Any, pack
from hypercorn.asyncio import serve as hypercorn_serve
from hypercorn.config import Config as HypercornConfig
from hypercorn.logging import Logger


def _create_request_info(
    ctx: ServiceContext, reqs: list[Any]
) -> ConformancePayload.RequestInfo:
    request_info = ConformancePayload.RequestInfo(requests=reqs)
    timeout_ms = ctx.timeout_ms()
    if timeout_ms is not None:
        request_info.timeout_ms = int(timeout_ms)
    for key, values in ctx.request_headers().items():
        request_info.request_headers.add(name=key, value=values)
    return request_info


def _convert_code(conformance_code: ConformanceCode) -> Code:
    match conformance_code:
        case ConformanceCode.CODE_CANCELED:
            return Code.CANCELED
        case ConformanceCode.CODE_UNKNOWN:
            return Code.UNKNOWN
        case ConformanceCode.CODE_INVALID_ARGUMENT:
            return Code.INVALID_ARGUMENT
        case ConformanceCode.CODE_DEADLINE_EXCEEDED:
            return Code.DEADLINE_EXCEEDED
        case ConformanceCode.CODE_NOT_FOUND:
            return Code.NOT_FOUND
        case ConformanceCode.CODE_ALREADY_EXISTS:
            return Code.ALREADY_EXISTS
        case ConformanceCode.CODE_PERMISSION_DENIED:
            return Code.PERMISSION_DENIED
        case ConformanceCode.CODE_RESOURCE_EXHAUSTED:
            return Code.RESOURCE_EXHAUSTED
        case ConformanceCode.CODE_FAILED_PRECONDITION:
            return Code.FAILED_PRECONDITION
        case ConformanceCode.CODE_ABORTED:
            return Code.ABORTED
        case ConformanceCode.CODE_OUT_OF_RANGE:
            return Code.OUT_OF_RANGE
        case ConformanceCode.CODE_UNIMPLEMENTED:
            return Code.UNIMPLEMENTED
        case ConformanceCode.CODE_INTERNAL:
            return Code.INTERNAL
        case ConformanceCode.CODE_UNAVAILABLE:
            return Code.UNAVAILABLE
        case ConformanceCode.CODE_DATA_LOSS:
            return Code.DATA_LOSS
        case ConformanceCode.CODE_UNAUTHENTICATED:
            return Code.UNAUTHENTICATED
    raise ValueError(f"Unknown ConformanceCode: {conformance_code}")


RES = TypeVar("RES", bound=UnaryResponse | IdempotentUnaryResponse)


async def _handle_unary_response(
    definition: UnaryResponseDefinition,
    reqs: list[Any],
    res: RES,
    ctx: ServiceContext,
) -> RES:
    for header in definition.response_headers:
        for value in header.value:
            ctx.add_response_header(header.name, value)
    for trailer in definition.response_trailers:
        for value in trailer.value:
            ctx.add_response_trailer(trailer.name, value)

    request_info = _create_request_info(ctx, reqs)

    if definition.WhichOneof("response") == "error":
        raise ConnecpyServerException(
            code=_convert_code(definition.error.code),
            message=definition.error.message,
            details=[*definition.error.details, request_info],
        )
    if definition.response_delay_ms:
        await asyncio.sleep(definition.response_delay_ms / 1000.0)

    res.payload.request_info.CopyFrom(request_info)
    res.payload.data = definition.response_data
    return res


class TestService(ConformanceService):
    async def Unary(self, req: UnaryRequest, ctx: ServiceContext) -> UnaryResponse:
        return await _handle_unary_response(
            req.response_definition, [pack(req)], UnaryResponse(), ctx
        )

    async def IdempotentUnary(
        self, req: IdempotentUnaryRequest, ctx: ServiceContext
    ) -> IdempotentUnaryResponse:
        return await _handle_unary_response(
            req.response_definition, [pack(req)], IdempotentUnaryResponse(), ctx
        )


class TestServiceSync(ConformanceServiceSync):
    _delegate = TestService()

    def Unary(self, req: UnaryRequest, ctx: ServiceContext) -> UnaryResponse:
        return asyncio.run(self._delegate.Unary(req, ctx))

    def IdempotentUnary(
        self, req: IdempotentUnaryRequest, ctx: ServiceContext
    ) -> IdempotentUnaryResponse:
        return asyncio.run(self._delegate.IdempotentUnary(req, ctx))


class PortCapturingLogger(Logger):
    """In-memory logger for Hypercorn, useful for testing."""

    port = -1

    def __init__(self, conf: HypercornConfig) -> None:
        super().__init__(conf)

    async def info(self, message: str, *args: Any, **kwargs: Any) -> None:
        if "Running on" in message:
            _, _, rest = message.partition("//127.0.0.1:")
            port, _, _ = rest.partition(" ")
            self.port = int(port)
        await super().info(message, *args, **kwargs)


async def serve(
    request: ServerCompatRequest, mode: Literal["sync", "async"]
) -> tuple[asyncio.Task, int]:
    match mode:
        case "async":
            app = ConformanceServiceASGIApplication(TestService())
        case "sync":
            app = ConformanceServiceWSGIApplication(TestServiceSync())

    conf = HypercornConfig()
    conf.bind = ["127.0.0.1:0"]

    cleanup = ExitStack()
    if request.use_tls:
        cert_file = cleanup.enter_context(NamedTemporaryFile(delete_on_close=False))
        key_file = cleanup.enter_context(NamedTemporaryFile(delete_on_close=False))
        cert_file.write(request.server_creds.cert)
        cert_file.close()
        key_file.write(request.server_creds.key)
        key_file.close()
        conf.certfile = cert_file.name
        conf.keyfile = key_file.name

    conf._log = PortCapturingLogger(conf)

    shutdown_event = asyncio.Event()

    def _signal_handler(*_) -> None:
        cleanup.close()
        shutdown_event.set()

    loop = asyncio.get_event_loop()
    loop.add_signal_handler(signal.SIGTERM, _signal_handler)
    loop.add_signal_handler(signal.SIGINT, _signal_handler)

    serve_task = loop.create_task(
        hypercorn_serve(
            app,  # pyright:ignore[reportArgumentType] - some incompatibility in type
            conf,
            shutdown_trigger=shutdown_event.wait,
            mode="asgi" if mode == "async" else "wsgi",
        )
    )
    port = -1
    for _ in range(100):
        port = conf._log.port
        if port != -1:
            break
        await asyncio.sleep(0.01)
    return serve_task, port


class Args(argparse.Namespace):
    mode: Literal["sync", "async"]


async def main():
    parser = argparse.ArgumentParser(description="Conformance client")
    parser.add_argument("--mode", choices=["sync", "async"])
    args = parser.parse_args(namespace=Args())

    stdin, stdout = await create_standard_streams()
    try:
        size_buf = await stdin.readexactly(4)
    except asyncio.IncompleteReadError:
        return
    size = int.from_bytes(size_buf)
    # Allow to raise even on EOF since we always should have a message
    request_buf = await stdin.readexactly(size)
    request = ServerCompatRequest()
    request.ParseFromString(request_buf)

    serve_task, port = await serve(request, args.mode)
    response = ServerCompatResponse()
    response.host = "127.0.0.1"
    response.port = port
    if request.use_tls:
        response.pem_cert = request.server_creds.cert
    response_buf = response.SerializeToString()
    size_buf = len(response_buf).to_bytes(4)
    stdout.write(size_buf)
    stdout.write(response_buf)
    await stdout.drain()
    # Runner will send sigterm which is handled by serve
    await serve_task


if __name__ == "__main__":
    asyncio.run(main())
