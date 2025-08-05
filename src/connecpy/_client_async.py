from asyncio import CancelledError, sleep, wait_for
from typing import AsyncIterator, Generic, Iterable, Mapping, Optional, TypeVar

import httpx
from google.protobuf.message import Message
from httpx import Response, Timeout

from . import _client_shared
from ._codec import Codec, get_proto_binary_codec, get_proto_json_codec
from ._compression import Compression, get_compression
from ._envelope import EnvelopeReader, EnvelopeWriter
from ._protocol import CONNECT_STREAMING_HEADER_COMPRESSION, ConnectWireError
from .code import Code
from .exceptions import ConnecpyException
from .headers import Headers

_RES = TypeVar("_RES", bound=Message)


class ConnecpyClient:
    """
    Represents an asynchronous client for Connecpy using httpx.

    Args:
        address (str): The address of the Connecpy server.
        timeout_ms (int): The timeout in ms for the overall request.
        session (httpx.AsyncClient): The httpx client session to use for making requests. If setting timeout_ms,
            the session should have timeout disabled or set higher than timeout_ms.
    """

    def __init__(
        self,
        address: str,
        proto_json: bool = False,
        accept_compression: Optional[Iterable[str]] = None,
        send_compression: Optional[str] = None,
        timeout_ms: Optional[int] = None,
        session: Optional[httpx.AsyncClient] = None,
    ) -> None:
        self._address = address
        self._codec = get_proto_json_codec() if proto_json else get_proto_binary_codec()
        self._timeout_ms = timeout_ms
        self._accept_compression = accept_compression
        self._send_compression = send_compression
        if session:
            self._session = session
            self._close_client = False
        else:
            self._session = httpx.AsyncClient(
                timeout=_convert_connect_timeout(timeout_ms)
            )
            self._close_client = True
        self._closed = False

    async def close(self):
        """Close the HTTP client. After closing, the client cannot be used to make requests."""
        if not self._closed:
            self._closed = True
            if self._close_client:
                await self._session.aclose()

    async def __aenter__(self):
        return self

    async def __aexit__(self, _exc_type, _exc_value, _traceback):
        await self.close()

    async def _make_request(
        self,
        *,
        url: str,
        request: Message,
        response_class: type[_RES],
        method="POST",
        headers: Headers | Mapping[str, str] | None = None,
        timeout_ms: Optional[int] = None,
    ) -> _RES:
        """Make an HTTP request to the server."""
        # Prepare headers and request args using shared logic
        request_args = {}
        if timeout_ms is None:
            timeout_ms = self._timeout_ms
        else:
            timeout = _convert_connect_timeout(timeout_ms)
            request_args["timeout"] = timeout

        request_headers = _client_shared.prepare_headers(
            self._codec,
            False,
            headers,
            timeout_ms,
            self._accept_compression,
            self._send_compression,
        )
        timeout_s = timeout_ms / 1000.0 if timeout_ms is not None else None

        try:
            request_data = self._codec.encode(request)
            client = self._session

            request_data, _ = _client_shared.maybe_compress_request(
                request_data, request_headers
            )

            if method == "GET":
                params = _client_shared.prepare_get_params(
                    self._codec, request_data, request_headers
                )
                request_headers.pop("content-type", None)
                resp = await wait_for(
                    client.get(
                        url=self._address + url,
                        headers=request_headers,
                        params=params,
                        **request_args,
                    ),
                    timeout_s,
                )
            else:
                resp = await wait_for(
                    client.post(
                        url=self._address + url,
                        headers=request_headers,
                        content=request_data,
                        **request_args,
                    ),
                    timeout_s,
                )

            _client_shared.validate_response_content_encoding(
                resp.headers.get("content-encoding", "")
            )
            _client_shared.validate_response_content_type(
                self._codec.name(),
                resp.status_code,
                resp.headers.get("content-type", ""),
            )
            _client_shared.handle_response_headers(resp.headers)

            if resp.status_code == 200:
                response = response_class()
                self._codec.decode(resp.content, response)
                return response
            else:
                raise ConnectWireError.from_response(resp).to_exception()
        except (httpx.TimeoutException, TimeoutError):
            raise ConnecpyException(Code.DEADLINE_EXCEEDED, "Request timed out")
        except ConnecpyException:
            raise
        except CancelledError as e:
            raise ConnecpyException(Code.CANCELED, "Request was cancelled") from e
        except Exception as e:
            raise ConnecpyException(Code.UNAVAILABLE, str(e))

    async def _make_request_stream(
        self,
        *,
        url: str,
        request: Message | AsyncIterator[Message],
        response_class: type[_RES],
        headers: Headers | Mapping[str, str] | None = None,
        timeout_ms: Optional[int] = None,
    ) -> "ResponseStream[_RES]":
        """Make an HTTP request to the server."""
        # Prepare headers and request args using shared logic
        request_args = {}
        if timeout_ms is None:
            timeout_ms = self._timeout_ms
        else:
            timeout = _convert_connect_timeout(timeout_ms)
            request_args["timeout"] = timeout

        request_headers = _client_shared.prepare_headers(
            self._codec,
            True,
            headers,
            timeout_ms,
            self._accept_compression,
            self._send_compression,
        )
        timeout_s = timeout_ms / 1000.0 if timeout_ms is not None else None

        try:
            request_data = _streaming_request_content(
                request, self._codec, self._send_compression
            )

            client = self._session

            resp = await wait_for(
                client.post(
                    url=self._address + url,
                    headers=request_headers,
                    content=request_data,
                    **request_args,
                ),
                timeout_s,
            )

            compression = _client_shared.validate_response_content_encoding(
                resp.headers.get(CONNECT_STREAMING_HEADER_COMPRESSION, "")
            )
            _client_shared.validate_stream_response_content_type(
                self._codec.name(),
                resp.headers.get("content-type", ""),
            )
            _client_shared.handle_response_headers(resp.headers)

            if resp.status_code == 200:
                return ResponseStream(resp, response_class, self._codec, compression)
            else:
                raise ConnectWireError.from_response(resp).to_exception()
        except (httpx.TimeoutException, TimeoutError):
            raise ConnecpyException(Code.DEADLINE_EXCEEDED, "Request timed out")
        except ConnecpyException:
            raise
        except CancelledError as e:
            raise ConnecpyException(Code.CANCELED, "Request was cancelled") from e
        except Exception as e:
            raise ConnecpyException(Code.UNAVAILABLE, str(e))

    async def _consume_single_response(self, stream: "ResponseStream[_RES]") -> _RES:
        res = None
        async for message in stream:
            if res is not None:
                raise ConnecpyException(
                    Code.UNIMPLEMENTED, "unary response has multiple messages"
                )
            res = message
        if res is None:
            raise ConnecpyException(
                Code.UNIMPLEMENTED, "unary response has zero messages"
            )
        return res


def _convert_connect_timeout(timeout_ms: Optional[int]) -> Timeout:
    if timeout_ms is None:
        # If no timeout provided, match connect-go's default behavior of a 30s connect timeout
        # and no read/write timeouts.
        return Timeout(None, connect=30.0)
    # We apply the timeout to the entire operation per connect's semantics so don't need
    # HTTP timeout
    return Timeout(None)


async def _streaming_request_content(
    msgs: Message | AsyncIterator[Message],
    codec: Codec,
    compression_name: Optional[str],
) -> AsyncIterator[bytes]:
    writer = EnvelopeWriter(codec, get_compression(compression_name or "identity"))

    if isinstance(msgs, Message):
        yield writer.write(msgs)
        return

    async for msg in msgs:
        yield writer.write(msg)


class ResponseStream(Generic[_RES]):
    """A streaming response from the server.

    A stream is associated with resources which must be cleaned up. If doing
    a simple iteration on all response messages with `async for`, the stream will
    be cleaned up automatically. If you only partially iterate, using `break` to
    interrupt it, make sure to use the response as a context manager or call
    `close()` to release resources.
    """

    def __init__(
        self,
        response: Response,
        response_class: type[_RES],
        codec: Codec,
        compression: Compression,
    ):
        self._response = response
        self._response_class = response_class
        self._codec = codec
        self._compression = compression
        self._closed = False

    async def __aiter__(self) -> AsyncIterator[_RES]:
        if self._closed:
            return

        reader = EnvelopeReader(self._response_class, self._codec, self._compression)
        try:
            async for chunk in self._response.aiter_bytes():
                for message in reader.feed(chunk):
                    yield message
                    # Check for cancellation each message. While this seems heavyweight,
                    # conformance tests require it.
                    await sleep(0)
        except CancelledError as e:
            raise ConnecpyException(Code.CANCELED, "Request was cancelled") from e
        finally:
            await self.close()

    async def close(self):
        """Close the stream and release resources."""
        if self._closed:
            return
        self._closed = True
        await self._response.aclose()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
